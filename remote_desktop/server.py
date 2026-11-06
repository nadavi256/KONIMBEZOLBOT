"""
Relay server for the remote desktop system.

Both the host agent (the computer being controlled) and the viewer (browser)
connect *out* to this server over WebSocket, so neither side needs open ports
or port forwarding - the same model AnyDesk / TeamViewer use.

    viewer (browser) <--wss--> server.py <--wss--> host.py (controlled PC)

Run:
    SITE_PASSWORD='...' python server.py --port 8080
    python server.py --port 443 --cert cert.pem --key key.pem   # TLS (recommended)

SITE_PASSWORD gates the website and the EXE downloads. Leave it unset and those
pages stay closed. /health, /ws/host, and /ws/viewer do not use it.
"""

import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import ssl
import time
from html import escape
from pathlib import Path

import aiohttp
from aiohttp import WSMsgType, web

log = logging.getLogger("relay")

STATIC_DIR = Path(__file__).parent / "static"
LOGIN_HTML = (STATIC_DIR / "login.html").read_text(encoding="utf-8")

# Website gate. This is not ACCESS_KEY and not the per-session host password.
# Empty means the landing page, viewer page, and downloads stay closed.
COOKIE_NAME = "site_auth"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60
NO_STORE = {"Cache-Control": "no-store"}

# Fetched server-side after a valid site cookie. Never embed these in HTML
# that an anonymous visitor can read.
DOWNLOADS = {
    "support": (
        "https://github.com/nadavi256/KONIMBEZOLBOT/releases/latest/download/RemoteSupport.exe",
        "RemoteSupport.exe",
    ),
    "control": (
        "https://github.com/nadavi256/KONIMBEZOLBOT/releases/latest/download/RemoteControl.exe",
        "RemoteControl.exe",
    ),
}

def configured_site_password(raw: str | None = None) -> str:
    """Return the website password, or "" when the site must stay closed."""
    if raw is None:
        raw = os.environ.get("SITE_PASSWORD") or ""
    return raw.strip()


def passwords_match(given: str, expected: str) -> bool:
    # An unset SITE_PASSWORD must not accept an empty login.
    if not expected or not given:
        return False
    return hmac.compare_digest(
        hashlib.sha256(given.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )


def make_token(password: str, now: float | None = None) -> str:
    exp = int((now if now is not None else time.time()) + COOKIE_MAX_AGE)
    payload = f"v1.{exp}"
    sig = hmac.new(password.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def token_valid(password: str, token: str, now: float | None = None) -> bool:
    if not password or not token or token.count(".") != 2:
        return False
    version, exp_s, sig = token.split(".")
    payload = f"{version}.{exp_s}"
    if version != "v1":
        return False
    expected = hmac.new(password.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if len(sig) != len(expected) or not hmac.compare_digest(sig, expected):
        return False
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    return exp > int(now if now is not None else time.time())


def request_is_https(request: web.Request) -> bool:
    # Render terminates TLS and forwards the browser scheme in this header.
    forwarded = request.headers.get("X-Forwarded-Proto", "")
    if forwarded:
        return forwarded.split(",")[0].strip().lower() == "https"
    for element in request.headers.get("Forwarded", "").split(","):
        for part in element.replace(" ", "").split(";"):
            if part.lower() == "proto=https":
                return True
    return request.scheme == "https"


def safe_next(raw: str) -> str:
    """Local path only, so the login form cannot redirect off this site."""
    if not raw or len(raw) > 512:
        return "/"
    if any(ord(ch) < 32 or ch == "\\" for ch in raw):
        return "/"
    if not raw.startswith("/") or raw.startswith("//"):
        return "/"
    return raw


def client_is_authed(request: web.Request) -> bool:
    password = request.app["site_password"]
    if not password:
        return False
    return token_valid(password, request.cookies.get(COOKIE_NAME, ""))


def current_next(request: web.Request) -> str:
    raw = request.path
    if request.query_string:
        raw = f"{raw}?{request.query_string}"
    return safe_next(raw)


def login_response(next_url: str, *, error: bool, status: int = 200) -> web.Response:
    error_html = '<p class="err" role="alert">סיסמה שגויה</p>' if error else ""
    html = (
        LOGIN_HTML
        .replace("__NEXT__", escape(safe_next(next_url), quote=True))
        .replace("__ERROR__", error_html)
    )
    return web.Response(
        text=html,
        status=status,
        content_type="text/html",
        charset="utf-8",
        headers=NO_STORE,
    )


def plain(status: int, text: str) -> web.Response:
    return web.Response(
        status=status,
        text=text,
        content_type="text/plain",
        charset="utf-8",
        headers=NO_STORE,
    )


async def login_get(request: web.Request) -> web.Response:
    nxt = safe_next(request.query.get("next", "/"))
    if client_is_authed(request):
        raise web.HTTPFound(nxt)
    return login_response(nxt, error=False)


async def login_post(request: web.Request) -> web.Response:
    data = await request.post()
    nxt = safe_next(str(data.get("next", "/")))
    given = str(data.get("password", ""))
    expected = request.app["site_password"]
    if not passwords_match(given, expected):
        log.info("site login failed from %s", request.remote)
        return login_response(nxt, error=True, status=401)
    resp = web.HTTPFound(nxt)
    resp.set_cookie(
        COOKIE_NAME,
        make_token(expected),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=request_is_https(request),
        samesite="Lax",
        path="/",
    )
    resp.headers["Cache-Control"] = "no-store"
    return resp


async def gated_page(request: web.Request, filename: str) -> web.StreamResponse:
    if not client_is_authed(request):
        return login_response(current_next(request), error=False)
    return web.FileResponse(
        STATIC_DIR / filename,
        headers={"Cache-Control": "private, no-store"},
    )


async def index(request: web.Request) -> web.StreamResponse:
    return await gated_page(request, "index.html")


async def viewer_page(request: web.Request) -> web.StreamResponse:
    return await gated_page(request, "viewer.html")


async def download(request: web.Request, kind: str) -> web.StreamResponse:
    if not client_is_authed(request):
        return plain(401, "נדרשת סיסמה")
    item = request.app["downloads"].get(kind)
    if item is None:
        return plain(404, "לא נמצא")
    url, filename = item
    session: aiohttp.ClientSession = request.app["http"]
    started = False
    try:
        async with session.get(url, allow_redirects=True) as upstream:
            if upstream.status != 200:
                log.warning("exe download failed status=%s kind=%s", upstream.status, kind)
                return plain(502, "ההורדה אינה זמינה כרגע")
            headers = {
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            }
            if upstream.content_length is not None:
                headers["Content-Length"] = str(upstream.content_length)
            stream = web.StreamResponse(status=200, headers=headers)
            await stream.prepare(request)
            started = True
            async for chunk in upstream.content.iter_chunked(64 * 1024):
                await stream.write(chunk)
            await stream.write_eof()
            return stream
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        log.warning("exe download error kind=%s err=%s", kind, type(exc).__name__)
        if started:
            raise
        return plain(502, "ההורדה אינה זמינה כרגע")


async def download_support(request: web.Request) -> web.StreamResponse:
    return await download(request, "support")


async def download_control(request: web.Request) -> web.StreamResponse:
    return await download(request, "control")


async def on_startup(app: web.Application) -> None:
    app["http"] = aiohttp.ClientSession(
        headers={"User-Agent": "remote-support"},
        timeout=aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=120),
    )


async def on_cleanup(app: web.Application) -> None:
    session = app.get("http")
    if session is not None:
        await session.close()


MAX_FAILED_ATTEMPTS = 5          # wrong passwords before a host ID is locked
LOCKOUT_SECONDS = 300            # how long the lock lasts
AUTH_TIMEOUT_SECONDS = 60        # time the host has to approve a session
MAX_INPUT_MSG_BYTES = 64 * 1024  # viewer -> host messages are small JSON (text paste can be ~12KB)
HEARTBEAT_SECONDS = 10           # detect dead connections within ~15s


class Host:
    def __init__(self, host_id: str, ws: web.WebSocketResponse, name: str, secret: str):
        self.id = host_id
        self.ws = ws
        self.name = name
        self.secret = secret  # proves a re-registering host is the same machine
        self.viewer: web.WebSocketResponse | None = None
        self.pending: dict[str, asyncio.Future] = {}
        self.failed = 0
        self.locked_until = 0.0


class Relay:
    def __init__(self, access_key: str | None):
        self.hosts: dict[str, Host] = {}
        self.access_key = access_key  # optional shared key hosts must present

    # ---------------------------------------------------------------- host --
    async def host_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=HEARTBEAT_SECONDS, max_msg_size=16 * 1024 * 1024)
        await ws.prepare(request)
        host: Host | None = None
        try:
            first = await ws.receive_json(timeout=15)
            if first.get("type") != "register":
                await ws.close(message=b"expected register")
                return ws
            if self.access_key and not secrets.compare_digest(
                str(first.get("access_key", "")), self.access_key
            ):
                await ws.send_json({"type": "error", "error": "bad access key"})
                await ws.close()
                return ws

            host_id = str(first.get("id", ""))
            if not (host_id.isdigit() and 6 <= len(host_id) <= 12):
                await ws.send_json({"type": "error", "error": "invalid id"})
                await ws.close()
                return ws
            secret = str(first.get("secret", ""))
            old = self.hosts.get(host_id)
            if old is not None:
                # Same machine reconnecting after a network drop: replace the
                # stale connection. Anyone else trying to grab the ID is refused.
                if not (secret and secrets.compare_digest(secret, old.secret)):
                    await ws.send_json({"type": "error", "error": "id in use"})
                    await ws.close()
                    return ws
                log.info("host %s reconnected, replacing stale connection", host_id)
                self.hosts.pop(host_id, None)
                await old.ws.close()

            host = Host(host_id, ws, str(first.get("name", ""))[:64], secret)
            if old is not None:
                host.failed, host.locked_until = old.failed, old.locked_until
            self.hosts[host_id] = host
            await ws.send_json({"type": "registered", "id": host_id})
            log.info("host %s registered (%s)", host_id, request.remote)

            async for msg in ws:
                if msg.type == WSMsgType.BINARY:
                    # screen frame -> forward to the viewer
                    if host.viewer is not None and not host.viewer.closed:
                        try:
                            await host.viewer.send_bytes(msg.data)
                        except ConnectionResetError:
                            pass
                elif msg.type == WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    t = data.get("type")
                    if t == "auth_result":
                        fut = host.pending.pop(data.get("sid", ""), None)
                        if fut and not fut.done():
                            fut.set_result(data)
                    elif t in ("screen_info", "session_end", "clipboard") and host.viewer:
                        await host.viewer.send_str(msg.data)
                elif msg.type == WSMsgType.ERROR:
                    break
        except (asyncio.TimeoutError, json.JSONDecodeError, TypeError):
            pass
        finally:
            if host is not None:
                if self.hosts.get(host.id) is host:
                    self.hosts.pop(host.id, None)
                for fut in host.pending.values():
                    if not fut.done():
                        fut.set_result({"ok": False, "reason": "host offline"})
                if host.viewer is not None and not host.viewer.closed:
                    # close without a session_end so the viewer auto-reconnects
                    # once the host is back
                    await host.viewer.close(code=4001, message=b"host connection lost")
                log.info("host %s disconnected", host.id)
        return ws

    # -------------------------------------------------------------- viewer --
    async def viewer_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=HEARTBEAT_SECONDS, max_msg_size=MAX_INPUT_MSG_BYTES)
        await ws.prepare(request)
        host: Host | None = None
        try:
            first = await ws.receive_json(timeout=30)
            host_id = str(first.get("id", "")).replace(" ", "")
            password = str(first.get("password", ""))
            host = self.hosts.get(host_id)

            if host is None:
                await ws.send_json({"type": "error", "error": "המחשב לא מחובר או שהמזהה שגוי"})
                return ws
            if time.time() < host.locked_until:
                await ws.send_json({"type": "error", "error": "יותר מדי ניסיונות שגויים, נסה מאוחר יותר"})
                return ws

            await ws.send_json({"type": "waiting", "message": "ממתין לאישור בצד המחשב המרוחק..."})
            sid = secrets.token_hex(8)
            fut = asyncio.get_running_loop().create_future()
            host.pending[sid] = fut
            await host.ws.send_json({
                "type": "auth",
                "sid": sid,
                "password": password,
                "resume": str(first.get("resume", ""))[:128],
                "remote": request.remote,
            })
            try:
                result = await asyncio.wait_for(fut, AUTH_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                host.pending.pop(sid, None)
                result = {"ok": False, "reason": "לא התקבל אישור בזמן"}

            if not result.get("ok"):
                if result.get("reason") == "bad password":
                    host.failed += 1
                    if host.failed >= MAX_FAILED_ATTEMPTS:
                        host.locked_until = time.time() + LOCKOUT_SECONDS
                        host.failed = 0
                        log.warning("host %s locked after failed attempts", host.id)
                    reason = "סיסמה שגויה"
                elif result.get("reason") == "rejected":
                    reason = "המשתמש בצד המרוחק דחה את החיבור"
                else:
                    reason = result.get("reason", "החיבור נדחה")
                await ws.send_json({"type": "error", "error": reason})
                return ws

            if self.hosts.get(host.id) is not host:  # host reconnected meanwhile
                host = self.hosts.get(host.id)
                if host is None:
                    await ws.send_json({"type": "error", "error": "המחשב התנתק"})
                    return ws

            # Approved (password + customer consent, or a valid resume token).
            # If an older viewer is still attached - e.g. a dead connection the
            # server hasn't noticed yet - it is replaced by this one.
            old_viewer = host.viewer
            host.failed = 0
            host.viewer = ws
            if old_viewer is not None and not old_viewer.closed:
                try:
                    await old_viewer.send_json({"type": "session_end", "reason": "החיבור עבר לחלון אחר"})
                    await old_viewer.close()
                except ConnectionError:
                    pass
            await ws.send_json({"type": "connected", "name": host.name, "resume": result.get("resume", "")})
            await host.ws.send_json({"type": "session_start"})
            log.info("session started on host %s from %s", host.id, request.remote)

            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    if msg.data == '{"type":"ping"}':  # viewer keep-alive, answered here
                        await ws.send_str('{"type":"pong"}')
                    elif not host.ws.closed:
                        await host.ws.send_str(msg.data)
                elif msg.type == WSMsgType.ERROR:
                    break
        except (asyncio.TimeoutError, json.JSONDecodeError, TypeError):
            pass
        finally:
            if host is not None and host.viewer is ws:
                host.viewer = None
                if not host.ws.closed:
                    await host.ws.send_json({"type": "session_end"})
                log.info("session ended on host %s", host.id)
        return ws

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "hosts_online": len(self.hosts)})


def build_app(
    access_key: str | None = None,
    site_password: str | None = None,
    download_urls: dict[str, str] | None = None,
) -> web.Application:
    site_password = configured_site_password(site_password)
    downloads: dict[str, tuple[str, str]] = {}
    for kind, (default_url, filename) in DOWNLOADS.items():
        url = default_url
        if download_urls and download_urls.get(kind):
            url = download_urls[kind]
        downloads[kind] = (url, filename)

    relay = Relay(access_key)
    app = web.Application()
    app["site_password"] = site_password
    app["downloads"] = downloads
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/", index)
    app.router.add_get("/viewer", viewer_page)
    app.router.add_get("/login", login_get)
    app.router.add_post("/login", login_post)
    app.router.add_get("/download/support", download_support)
    app.router.add_get("/download/control", download_control)
    app.router.add_get("/health", relay.health)
    app.router.add_get("/ws/host", relay.host_ws)
    app.router.add_get("/ws/viewer", relay.viewer_ws)
    return app


def main() -> None:
    p = argparse.ArgumentParser(description="Remote desktop relay server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    p.add_argument("--cert", help="TLS certificate (PEM)")
    p.add_argument("--key", help="TLS private key (PEM)")
    p.add_argument("--access-key", default=os.environ.get("ACCESS_KEY") or None,
                   help="shared key that host agents must present to register")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = build_app(args.access_key)
    if app["site_password"]:
        log.info("site password protection enabled")
    else:
        log.warning("SITE_PASSWORD is not set; landing page and downloads are closed")
    ssl_ctx = None
    if args.cert and args.key:
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain(args.cert, args.key)
    else:
        log.info("serving plain HTTP - put HTTPS in front of it (cloud hosts like Render do this)")

    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_ctx)


if __name__ == "__main__":
    main()
