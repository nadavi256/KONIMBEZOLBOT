"""
Relay server for the remote desktop system.

Both the host agent (the computer being controlled) and the viewer (browser)
connect *out* to this server over WebSocket, so neither side needs open ports
or port forwarding - the same model AnyDesk / TeamViewer use.

    viewer (browser) <--wss--> server.py <--wss--> host.py (controlled PC)

Run:
    python server.py --port 8080
    python server.py --port 443 --cert cert.pem --key key.pem   # TLS (recommended)
"""

import argparse
import asyncio
import json
import logging
import os
import secrets
import ssl
import time
from pathlib import Path

from aiohttp import WSMsgType, web

log = logging.getLogger("relay")

STATIC_DIR = Path(__file__).parent / "static"

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

    async def index(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / "index.html")

    async def viewer(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / "viewer.html")

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "hosts_online": len(self.hosts)})


def build_app(access_key: str | None = None) -> web.Application:
    relay = Relay(access_key)
    app = web.Application()
    app.router.add_get("/", relay.index)
    app.router.add_get("/viewer", relay.viewer)
    app.router.add_get("/health", relay.health)
    app.router.add_get("/ws/host", relay.host_ws)
    app.router.add_get("/ws/viewer", relay.viewer_ws)
    app.router.add_static("/static", STATIC_DIR)
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
    ssl_ctx = None
    if args.cert and args.key:
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain(args.cert, args.key)
    else:
        log.info("serving plain HTTP - put HTTPS in front of it (cloud hosts like Render do this)")

    web.run_app(build_app(args.access_key), host=args.host, port=args.port, ssl_context=ssl_ctx)


if __name__ == "__main__":
    main()
