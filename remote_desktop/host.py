"""
Host agent - runs on the computer that will be controlled.

It connects out to the relay server, shows a permanent ID and a one-time
password, and (by default) asks the person sitting at the computer to approve
every incoming session. While a session is active a window stays visible
with an "End session" button.

Run:
    python host.py --server wss://remote.example.com
    python host.py --server ws://192.168.1.10:8080 --console          # no GUI
    python host.py --server wss://... --password MyStrongPass --no-confirm   # unattended, your own PC only
"""

import argparse
import asyncio
import concurrent.futures
import hashlib
import hmac
import io
import json
import logging
import os
import platform
import queue
import secrets
import string
import sys
import threading
import time
from pathlib import Path

import aiohttp

log = logging.getLogger("host")

CONFIG_PATH = Path.home() / ".remote_desktop_host.json"


def bundled_config() -> dict:
    """config.json shipped inside the EXE (or next to host.py when run from source)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    try:
        return json.loads((base / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def to_ws_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url.startswith("https://"):
        return "wss://" + url[len("https://"):]
    if url.startswith("http://"):
        return "ws://" + url[len("http://"):]
    return url


def enable_dpi_awareness() -> None:
    """On Windows, make screen capture and mouse coordinates use real pixels."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def load_or_create_id() -> tuple[str, str]:
    """Permanent 9-digit ID plus a private secret that lets this machine
    reclaim its ID on the server after a network drop."""
    data: dict = {}
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (OSError, ValueError):
        pass
    host_id = str(data.get("id", ""))
    secret = str(data.get("secret", ""))
    if not host_id.isdigit():
        host_id = str(secrets.randbelow(900_000_000) + 100_000_000)  # 9 digits
    if len(secret) < 16:
        secret = secrets.token_urlsafe(24)
    if data.get("id") != host_id or data.get("secret") != secret:
        try:
            CONFIG_PATH.write_text(json.dumps({"id": host_id, "secret": secret}))
        except OSError:
            pass
    return host_id, secret


def setup_logging() -> Path | None:
    """Log to a file (the EXE has no console) so problems can be diagnosed."""
    import logging.handlers
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "RemoteSupport"
    handlers: list[logging.Handler] = []
    log_file = None
    try:
        base.mkdir(parents=True, exist_ok=True)
        log_file = base / "host.log"
        handlers.append(logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=1, encoding="utf-8"))
    except OSError:
        pass
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(message)s")
    return log_file


def random_password(n: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    alphabet = alphabet.translate(str.maketrans("", "", "0o1l"))  # avoid confusables
    return "".join(secrets.choice(alphabet) for _ in range(n))


def format_id(host_id: str) -> str:
    return " ".join(host_id[i:i + 3] for i in range(0, len(host_id), 3))


# --------------------------------------------------------------------- input --
class InputInjector:
    """Turns viewer events into real mouse / keyboard actions via pynput."""

    def __init__(self):
        from pynput import keyboard, mouse
        self.kb = keyboard
        self.mouse_mod = mouse
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()
        self.pressed: set = set()
        K = keyboard.Key
        self.special = {
            "Enter": K.enter, "Backspace": K.backspace, "Tab": K.tab, "Escape": K.esc,
            " ": K.space, "Delete": K.delete, "Insert": getattr(K, "insert", None),
            "Home": K.home, "End": K.end, "PageUp": K.page_up, "PageDown": K.page_down,
            "ArrowUp": K.up, "ArrowDown": K.down, "ArrowLeft": K.left, "ArrowRight": K.right,
            "Shift": K.shift, "Control": K.ctrl, "Alt": K.alt, "AltGraph": getattr(K, "alt_gr", K.alt),
            "Meta": K.cmd, "OS": K.cmd, "CapsLock": K.caps_lock,
            "ContextMenu": getattr(K, "menu", None), "PrintScreen": getattr(K, "print_screen", None),
            "NumLock": getattr(K, "num_lock", None), "ScrollLock": getattr(K, "scroll_lock", None),
            "Pause": getattr(K, "pause", None),
        }
        for i in range(1, 21):
            f = getattr(K, f"f{i}", None)
            if f is not None:
                self.special[f"F{i}"] = f
        self.buttons = {0: mouse.Button.left, 1: mouse.Button.middle, 2: mouse.Button.right}

    def _key(self, ev: dict):
        name = ev.get("key", "")
        if name in self.special:
            return self.special[name]
        if len(name) == 1:
            return self.kb.KeyCode.from_char(name)
        return None

    def handle(self, ev: dict, geom: dict) -> None:
        t = ev.get("type")
        if t in ("mouse_move", "mouse_down", "mouse_up") and "x" in ev:
            x = geom["left"] + max(0.0, min(1.0, float(ev["x"]))) * (geom["width"] - 1)
            y = geom["top"] + max(0.0, min(1.0, float(ev["y"]))) * (geom["height"] - 1)
            self.mouse.position = (int(x), int(y))
        if t == "mouse_down":
            self.mouse.press(self.buttons.get(ev.get("button", 0), self.mouse_mod.Button.left))
        elif t == "mouse_up":
            self.mouse.release(self.buttons.get(ev.get("button", 0), self.mouse_mod.Button.left))
        elif t == "wheel":
            def steps(v: float) -> int:  # browser deltas (~100/notch) -> wheel notches
                if v == 0:
                    return 0
                n = min(10, max(1, round(abs(v) / 100)))
                return n if v > 0 else -n
            # browsers: positive dy = scroll down; pynput: positive dy = scroll up
            self.mouse.scroll(steps(float(ev.get("dx", 0))), -steps(float(ev.get("dy", 0))))
        elif t == "key_down":
            k = self._key(ev)
            if k is not None:
                self.keyboard.press(k)
                self.pressed.add(k)
        elif t == "key_up":
            k = self._key(ev)
            if k is not None:
                self.keyboard.release(k)
                self.pressed.discard(k)
        elif t == "text":
            # pasted / composed text (e.g. Hebrew via the viewer's text box).
            # One char at a time with a short pause: on Linux pynput remaps a
            # spare keycode per character and drops chars if typed too fast.
            for ch in str(ev.get("text", ""))[:2000]:
                self.keyboard.type(ch)
                time.sleep(0.02)

    def release_all(self) -> None:
        for k in list(self.pressed):
            try:
                self.keyboard.release(k)
            except Exception:
                pass
        self.pressed.clear()


# -------------------------------------------------------------------- capture --
class ScreenCapturer:
    def __init__(self, monitor: int):
        import mss
        self.sct = getattr(mss, "MSS", mss.mss)()
        mons = self.sct.monitors
        self.monitor = mons[monitor] if 0 <= monitor < len(mons) else mons[1]
        self.last_digest = b""

    @property
    def geometry(self) -> dict:
        m = self.monitor
        return {"left": m["left"], "top": m["top"], "width": m["width"], "height": m["height"]}

    # classic arrow pointer, tip at (0, 0)
    ARROW = [(0, 0), (0, 17), (4, 13), (7, 20), (10, 19), (7, 12), (12, 12)]

    def cursor_pos(self) -> tuple[int, int] | None:
        """Mouse position in screen pixels. Screen capture on Windows does not
        include the cursor, so we draw it into the frame ourselves."""
        try:
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes
                pt = wintypes.POINT()
                if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                    return pt.x, pt.y
                return None
            if not hasattr(self, "_mouse"):
                from pynput.mouse import Controller
                self._mouse = Controller()
            x, y = self._mouse.position
            return int(x), int(y)
        except Exception:
            return None

    def grab_jpeg(self, quality: int, scale: float, force: bool) -> bytes | None:
        from PIL import Image, ImageDraw
        shot = self.sct.grab(self.monitor)
        cur = self.cursor_pos()
        if cur is not None:
            cur = (cur[0] - self.monitor["left"], cur[1] - self.monitor["top"])
            if not (0 <= cur[0] < shot.size[0] and 0 <= cur[1] < shot.size[1]):
                cur = None  # cursor is on another monitor
        h = hashlib.blake2b(shot.raw, digest_size=16)
        h.update(repr(cur).encode())  # a moving cursor alone also counts as a change
        digest = h.digest()
        if digest == self.last_digest and not force:
            return None  # nothing changed on screen
        self.last_digest = digest
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        if scale < 1.0:
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
        if cur is not None:
            k = max(1.0, img.width / 1600) if scale >= 1.0 else 1.0  # bigger arrow on big screens
            cx, cy = cur[0] * scale, cur[1] * scale
            pts = [(cx + x * k, cy + y * k) for x, y in self.ARROW]
            ImageDraw.Draw(img).polygon(pts, fill="white", outline="black")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=False)
        return buf.getvalue()


# ----------------------------------------------------------------- the agent --
class HostAgent:
    def __init__(self, args, ui):
        self.args = args
        self.ui = ui
        self.id, self.secret = load_or_create_id()
        self.password = args.password or random_password()
        self.session_active = False
        self.quality = 60
        self.scale = 1.0
        self.fps = 15
        self.in_flight = 0
        self.max_in_flight = 2
        self.force_frame = False
        self.injector = None
        self.capturer = None
        # mss must be created and used on one fixed thread (required on Windows)
        self.capture_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.ws: aiohttp.ClientWebSocketResponse | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        # After an approved session, the same viewer may reconnect without
        # asking the customer again (network drop) - for a limited time.
        self.resume_token = ""
        self.resume_until = 0.0

    # -- called from the UI thread
    def request_end_session(self) -> None:
        if self.loop and self.ws:
            asyncio.run_coroutine_threadsafe(self._end_session(), self.loop)

    async def _end_session(self) -> None:
        if self.ws and not self.ws.closed and self.session_active:
            await self.ws.send_json({"type": "session_end", "reason": "המשתמש בצד המרוחק סיים את החיבור"})
        self._session_stopped(allow_resume=False)  # customer ended it: no silent reconnect

    def _session_stopped(self, allow_resume: bool = True) -> None:
        if self.resume_token:
            self.resume_until = time.time() + 120 if allow_resume else 0.0
        if self.session_active:
            log.info("session stopped (resume allowed: %s)", allow_resume)
            self.session_active = False
            if self.injector:
                self.injector.release_all()
            self.ui.status("מוכן, ממתין לטכנאי", active=False)

    async def run(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.ui.show_credentials(format_id(self.id), self.password)
        backoff = 1
        while True:
            try:
                await self._connect_once()
                backoff = 1
                log.info("connection to server closed")
            except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as e:
                log.info("server connection error: %r", e)
                self.ui.status("אין חיבור לאינטרנט/שרת, מנסה שוב...", active=False)
            except Exception:
                log.exception("unexpected error in connection loop")
                self.ui.status("מתחבר מחדש...", active=False)
            self._session_stopped()
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    async def _connect_once(self) -> None:
        url = to_ws_url(self.args.server) + "/ws/host"
        async with aiohttp.ClientSession() as http:
            async with http.ws_connect(url, heartbeat=10, max_msg_size=1024 * 1024) as ws:
                self.ws = ws
                await ws.send_json({
                    "type": "register", "id": self.id, "secret": self.secret,
                    "name": platform.node(), "access_key": self.args.access_key or "",
                })
                reply = await ws.receive_json(timeout=15)
                if reply.get("type") != "registered":
                    self.ui.status(f"השרת דחה את הרישום: {reply.get('error')}", active=False)
                    await asyncio.sleep(10)
                    return
                log.info("registered on server as %s", self.id)
                self.ui.status("מוכן, ממתין לטכנאי", active=False)
                stream_task = asyncio.create_task(self._stream_loop())
                try:
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        try:
                            await self._on_message(json.loads(msg.data))
                        except (ConnectionError, aiohttp.ClientError):
                            raise
                        except Exception:  # one bad message must never drop the connection
                            log.exception("error handling message")
                finally:
                    stream_task.cancel()
                    self.ws = None

    async def _on_message(self, ev: dict) -> None:
        t = ev.get("type")
        if t == "auth":
            asyncio.create_task(self._authenticate(ev))
        elif t == "session_start":
            log.info("session start")
            # create the screen capturer BEFORE marking the session active,
            # otherwise the stream loop can run with no capturer yet
            if self.capturer is None:
                self.capturer = await self.loop.run_in_executor(
                    self.capture_pool, ScreenCapturer, self.args.monitor)
            self.in_flight = 0
            self.force_frame = True
            self.session_active = True
            g = self.capturer.geometry
            await self.ws.send_json({"type": "screen_info", "width": g["width"], "height": g["height"]})
            self.ui.status("הטכנאי מחובר ושולט במחשב", active=True)
        elif t == "session_end":
            log.info("session end from server")
            self._session_stopped()
        elif not self.session_active:
            return
        elif t == "ack":
            self.in_flight = max(0, self.in_flight - 1)
        elif t == "settings":
            self.quality = int(max(10, min(95, ev.get("quality", self.quality))))
            self.scale = float(max(0.25, min(1.0, ev.get("scale", self.scale))))
            self.fps = int(max(1, min(30, ev.get("fps", self.fps))))
            self.force_frame = True
        elif t == "refresh":
            self.force_frame = True
        elif self.args.view_only:
            return
        else:
            try:
                if self.injector is None:
                    self.injector = InputInjector()
                if t == "text":  # slow path, keep the event loop free
                    await asyncio.to_thread(self.injector.handle, ev, self.capturer.geometry)
                else:
                    self.injector.handle(ev, self.capturer.geometry)
            except Exception as e:  # never let a bad event kill the agent
                log.debug("input error: %s", e)

    async def _authenticate(self, ev: dict) -> None:
        sid = ev.get("sid")
        ok_pw = hmac.compare_digest(str(ev.get("password", "")).encode(), self.password.encode())
        if not ok_pw:
            log.info("auth rejected: bad password from %s", ev.get("remote"))
            await self.ws.send_json({"type": "auth_result", "sid": sid, "ok": False, "reason": "bad password"})
            return
        resume = str(ev.get("resume", ""))
        resuming = bool(
            resume and self.resume_token
            and hmac.compare_digest(resume.encode(), self.resume_token.encode())
            and (self.session_active or time.time() < self.resume_until)
        )
        if resuming:
            log.info("viewer resumed the session after a drop")
            await self.ws.send_json({"type": "auth_result", "sid": sid, "ok": True,
                                     "resume": self.resume_token})
            return
        if not self.args.no_confirm:
            accepted = await self.ui.ask_permission(ev.get("remote") or "?")
            if not accepted:
                await self.ws.send_json({"type": "auth_result", "sid": sid, "ok": False, "reason": "rejected"})
                return
        self.resume_token = secrets.token_urlsafe(16)
        self.resume_until = 0.0
        log.info("session approved for %s", ev.get("remote"))
        await self.ws.send_json({"type": "auth_result", "sid": sid, "ok": True, "resume": self.resume_token})

    async def _stream_loop(self) -> None:
        while True:
            await asyncio.sleep(1 / self.fps)
            if not self.session_active or self.ws is None or self.ws.closed:
                continue
            if self.in_flight >= self.max_in_flight and not self.force_frame:
                continue  # viewer hasn't caught up - don't build a backlog
            if self.capturer is None:
                continue
            force, self.force_frame = self.force_frame, False
            try:
                frame = await self.loop.run_in_executor(
                    self.capture_pool, self.capturer.grab_jpeg, self.quality, self.scale, force)
                if frame is None:
                    continue
                self.in_flight += 1
                await self.ws.send_bytes(frame)
            except (ConnectionError, aiohttp.ClientError):
                continue  # connection dropped; the main loop reconnects
            except Exception as e:  # never let one bad frame stop the stream
                log.warning("capture error: %s", e)
                self.force_frame = True
                await asyncio.sleep(0.5)


# ------------------------------------------------------------------------ UI --
class ConsoleUI:
    def show_credentials(self, host_id: str, password: str) -> None:
        print("=" * 44)
        print(f"  מזהה המחשב:  {host_id}")
        print(f"  סיסמה:       {password}")
        print("=" * 44, flush=True)

    def status(self, text: str, active: bool) -> None:
        print(f"[{'פעיל' if active else 'מצב'}] {text}", flush=True)

    async def ask_permission(self, remote: str) -> bool:
        def ask():
            return input(f"בקשת שליטה מרחוק מ-{remote}. לאשר? (y/n): ").strip().lower() in ("y", "yes", "כ", "כן")
        return await asyncio.to_thread(ask)


class TkUI:
    """Simple always-visible window: ID, password, status and an End-session button."""

    def __init__(self):
        import tkinter as tk
        self.tk = tk
        self.root = tk.Tk()
        self.root.title("תמיכה מרחוק")
        w, h = 380, 330
        x = self.root.winfo_screenwidth() - w - 24
        y = self.root.winfo_screenheight() - h - 80
        self.root.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        self.root.resizable(False, False)
        self.root.configure(bg="white")
        self.q: queue.Queue = queue.Queue()
        big = ("Segoe UI", 26, "bold")
        lbl = dict(bg="white", font=("Segoe UI", 11))
        tk.Label(self.root, text="הקריאו לטכנאי את המזהה והסיסמה", bg="white",
                 font=("Segoe UI", 12, "bold")).pack(pady=(14, 6))
        tk.Label(self.root, text="מזהה", **lbl).pack()
        self.id_var = tk.StringVar(value="...")
        tk.Label(self.root, textvariable=self.id_var, font=big, bg="white", fg="#1d4ed8").pack()
        tk.Label(self.root, text="סיסמה", **lbl).pack(pady=(6, 0))
        self.pw_var = tk.StringVar(value="...")
        tk.Label(self.root, textvariable=self.pw_var, font=big, bg="white", fg="#1d4ed8").pack()
        self.status_var = tk.StringVar(value="מתחבר לשרת")
        self.status_lbl = tk.Label(self.root, textvariable=self.status_var, bg="white",
                                   font=("Segoe UI", 11), pady=8)
        self.status_lbl.pack()
        self.end_btn = tk.Button(self.root, text="סיים חיבור", state="disabled", bg="#dc2626", fg="white",
                                 font=("Segoe UI", 11, "bold"), relief="flat", padx=16, pady=4)
        self.end_btn.pack()
        self.agent: HostAgent | None = None
        self.root.after(100, self._poll)

    def attach(self, agent: "HostAgent") -> None:
        self.agent = agent
        self.end_btn.configure(command=agent.request_end_session)

    # -- thread-safe API used by the agent
    def show_credentials(self, host_id: str, password: str) -> None:
        self.q.put(("creds", host_id, password))

    def status(self, text: str, active: bool) -> None:
        self.q.put(("status", text, active))

    async def ask_permission(self, remote: str) -> bool:
        fut: concurrent.futures.Future = concurrent.futures.Future()
        self.q.put(("ask", remote, fut))
        return await asyncio.wrap_future(fut)

    def _poll(self) -> None:
        from tkinter import messagebox
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "creds":
                    self.id_var.set(item[1])
                    self.pw_var.set(item[2])
                elif item[0] == "status":
                    self.status_var.set(item[1])
                    self.status_lbl.configure(fg="#dc2626" if item[2] else "#475569")
                    self.end_btn.configure(state="normal" if item[2] else "disabled")
                    self.root.attributes("-topmost", bool(item[2]))
                    if item[2]:
                        self.root.deiconify()
                elif item[0] == "ask":
                    self.root.deiconify()
                    self.root.lift()
                    self.root.attributes("-topmost", True)
                    ok = messagebox.askyesno("בקשת חיבור",
                                             "הטכנאי מבקש להתחבר למחשב שלך.\nלאשר?",
                                             parent=self.root)
                    self.root.attributes("-topmost", False)
                    item[2].set_result(ok)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def mainloop(self, agent: "HostAgent") -> None:
        threading.Thread(target=lambda: asyncio.run(agent.run()), daemon=True).start()
        self.root.mainloop()


def main() -> None:
    p = argparse.ArgumentParser(description="Remote desktop host agent")
    p.add_argument("--server", default=bundled_config().get("server_url") or None,
                   help="relay URL, e.g. https://remote.example.com (default: from config.json)")
    p.add_argument("--password", help="fixed password (default: new random password every run)")
    p.add_argument("--no-confirm", action="store_true",
                   help="do not ask for approval (unattended access - only on computers you own)")
    p.add_argument("--view-only", action="store_true", help="viewer can see but not control")
    p.add_argument("--monitor", type=int, default=1, help="monitor number (1 = primary)")
    p.add_argument("--access-key", help="relay access key, if the server requires one")
    p.add_argument("--console", action="store_true", help="no window, use the terminal")
    args = p.parse_args()

    if not args.server:
        p.error("no server configured: pass --server or set server_url in config.json")
    if args.password and len(args.password) < 8:
        p.error("password must be at least 8 characters")
    if args.no_confirm and not args.password:
        p.error("--no-confirm requires a fixed --password")

    log_file = setup_logging()
    log.info("starting host agent, server=%s, log=%s", args.server, log_file)
    enable_dpi_awareness()

    if args.console:
        ui = ConsoleUI()
        agent = HostAgent(args, ui)
        try:
            asyncio.run(agent.run())
        except KeyboardInterrupt:
            pass
    else:
        ui = TkUI()
        agent = HostAgent(args, ui)
        ui.attach(agent)
        ui.mainloop(agent)


if __name__ == "__main__":
    main()
