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


def enable_dpi_awareness() -> None:
    """On Windows, make screen capture and mouse coordinates use real pixels."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def load_or_create_id() -> str:
    try:
        data = json.loads(CONFIG_PATH.read_text())
        if str(data.get("id", "")).isdigit():
            return data["id"]
    except (OSError, ValueError):
        pass
    host_id = str(secrets.randbelow(900_000_000) + 100_000_000)  # 9 digits
    try:
        CONFIG_PATH.write_text(json.dumps({"id": host_id}))
    except OSError:
        pass
    return host_id


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

    def grab_jpeg(self, quality: int, scale: float, force: bool) -> bytes | None:
        from PIL import Image
        shot = self.sct.grab(self.monitor)
        digest = hashlib.blake2b(shot.raw, digest_size=16).digest()
        if digest == self.last_digest and not force:
            return None  # nothing changed on screen
        self.last_digest = digest
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        if scale < 1.0:
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=False)
        return buf.getvalue()


# ----------------------------------------------------------------- the agent --
class HostAgent:
    def __init__(self, args, ui):
        self.args = args
        self.ui = ui
        self.id = load_or_create_id()
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

    # -- called from the UI thread
    def request_end_session(self) -> None:
        if self.loop and self.ws:
            asyncio.run_coroutine_threadsafe(self._end_session(), self.loop)

    async def _end_session(self) -> None:
        if self.ws and not self.ws.closed and self.session_active:
            await self.ws.send_json({"type": "session_end", "reason": "המשתמש בצד המרוחק סיים את החיבור"})
        self._session_stopped()

    def _session_stopped(self) -> None:
        if self.session_active:
            self.session_active = False
            if self.injector:
                self.injector.release_all()
            self.ui.status("ממתין לחיבור", active=False)

    async def run(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.ui.show_credentials(format_id(self.id), self.password)
        backoff = 1
        while True:
            try:
                await self._connect_once()
                backoff = 1
            except (aiohttp.ClientError, OSError) as e:
                self.ui.status(f"אין חיבור לשרת ({e.__class__.__name__}), מנסה שוב...", active=False)
            self._session_stopped()
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    async def _connect_once(self) -> None:
        url = self.args.server.rstrip("/") + "/ws/host"
        async with aiohttp.ClientSession() as http:
            async with http.ws_connect(url, heartbeat=20, max_msg_size=64 * 1024) as ws:
                self.ws = ws
                await ws.send_json({
                    "type": "register", "id": self.id,
                    "name": platform.node(), "access_key": self.args.access_key or "",
                })
                reply = await ws.receive_json(timeout=15)
                if reply.get("type") != "registered":
                    self.ui.status(f"השרת דחה את הרישום: {reply.get('error')}", active=False)
                    await asyncio.sleep(10)
                    return
                self.ui.status("ממתין לחיבור", active=False)
                stream_task = asyncio.create_task(self._stream_loop())
                try:
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        await self._on_message(json.loads(msg.data))
                finally:
                    stream_task.cancel()
                    self.ws = None

    async def _on_message(self, ev: dict) -> None:
        t = ev.get("type")
        if t == "auth":
            asyncio.create_task(self._authenticate(ev))
        elif t == "session_start":
            self.session_active = True
            self.in_flight = 0
            self.force_frame = True
            if self.capturer is None:
                self.capturer = await self.loop.run_in_executor(
                    self.capture_pool, ScreenCapturer, self.args.monitor)
            g = self.capturer.geometry
            await self.ws.send_json({"type": "screen_info", "width": g["width"], "height": g["height"]})
            self.ui.status("⚠️ המחשב נשלט כרגע מרחוק", active=True)
        elif t == "session_end":
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
            await self.ws.send_json({"type": "auth_result", "sid": sid, "ok": False, "reason": "bad password"})
            return
        if not self.args.no_confirm:
            accepted = await self.ui.ask_permission(ev.get("remote") or "?")
            if not accepted:
                await self.ws.send_json({"type": "auth_result", "sid": sid, "ok": False, "reason": "rejected"})
                return
        await self.ws.send_json({"type": "auth_result", "sid": sid, "ok": True})

    async def _stream_loop(self) -> None:
        while True:
            await asyncio.sleep(1 / self.fps)
            if not self.session_active or self.ws is None or self.ws.closed:
                continue
            if self.in_flight >= self.max_in_flight and not self.force_frame:
                continue  # viewer hasn't caught up - don't build a backlog
            force, self.force_frame = self.force_frame, False
            frame = await self.loop.run_in_executor(
                self.capture_pool, self.capturer.grab_jpeg, self.quality, self.scale, force)
            if frame is None:
                continue
            self.in_flight += 1
            await self.ws.send_bytes(frame)


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
    """Small always-visible window: ID, password, status and an End-session button."""

    def __init__(self):
        import tkinter as tk
        self.tk = tk
        self.root = tk.Tk()
        self.root.title("שליטה מרחוק - מארח")
        self.root.geometry("340x230")
        self.root.attributes("-topmost", True)
        self.q: queue.Queue = queue.Queue()
        font_big = ("Segoe UI", 18, "bold")
        tk.Label(self.root, text="מזהה המחשב:").pack(pady=(10, 0))
        self.id_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.id_var, font=font_big, justify="center",
                 state="readonly", width=14).pack()
        tk.Label(self.root, text="סיסמה:").pack(pady=(6, 0))
        self.pw_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.pw_var, font=font_big, justify="center",
                 state="readonly", width=14).pack()
        self.status_var = tk.StringVar(value="מתחבר לשרת...")
        self.status_lbl = tk.Label(self.root, textvariable=self.status_var, pady=6)
        self.status_lbl.pack()
        self.end_btn = tk.Button(self.root, text="סיים חיבור", state="disabled", bg="#c62828", fg="white")
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
                    self.status_lbl.configure(fg="#c62828" if item[2] else "black")
                    self.end_btn.configure(state="normal" if item[2] else "disabled")
                    if item[2]:
                        self.root.deiconify()
                elif item[0] == "ask":
                    self.root.deiconify()
                    self.root.lift()
                    ok = messagebox.askyesno("בקשת שליטה מרחוק",
                                             f"מישהו ({item[1]}) מבקש לשלוט במחשב הזה.\nלאשר?",
                                             parent=self.root)
                    item[2].set_result(ok)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def mainloop(self, agent: "HostAgent") -> None:
        threading.Thread(target=lambda: asyncio.run(agent.run()), daemon=True).start()
        self.root.mainloop()


def main() -> None:
    p = argparse.ArgumentParser(description="Remote desktop host agent")
    p.add_argument("--server", required=True, help="relay URL, e.g. wss://remote.example.com")
    p.add_argument("--password", help="fixed password (default: new random password every run)")
    p.add_argument("--no-confirm", action="store_true",
                   help="do not ask for approval (unattended access - only on computers you own)")
    p.add_argument("--view-only", action="store_true", help="viewer can see but not control")
    p.add_argument("--monitor", type=int, default=1, help="monitor number (1 = primary)")
    p.add_argument("--access-key", help="relay access key, if the server requires one")
    p.add_argument("--console", action="store_true", help="no window, use the terminal")
    args = p.parse_args()

    if args.password and len(args.password) < 8:
        p.error("password must be at least 8 characters")
    if args.no_confirm and not args.password:
        p.error("--no-confirm requires a fixed --password")

    logging.basicConfig(level=logging.INFO)
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
