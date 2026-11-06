"""
End-to-end check used by CI on a real Windows machine:
starts the relay server, starts the built RemoteSupport.exe, connects as a
viewer, verifies a screen frame arrives and that the remote mouse moves.

The site-password gate is checked on every run, including without the exe:

    python smoke_test.py
    python smoke_test.py dist/RemoteSupport.exe
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from aiohttp.test_utils import TestClient, TestServer

from server import COOKIE_MAX_AGE, COOKIE_NAME, build_app, make_token

PORT = 8765
PASSWORD = "smoketest123"  # per-session host password, not the website password
SITE_PASSWORD = "smoketest-site-password"

_LEAKS = (
    "github.com",
    "remotesupport.exe",
    "remotecontrol.exe",
    "/download/support",
    "/download/control",
    "releases/latest",
    "הורדת תוכנת",
    "nadavi256",
)


def assert_no_download_leaks(text: str) -> None:
    lowered = text.lower()
    for needle in _LEAKS:
        assert needle not in lowered, needle


def assert_login_page(text: str, *, error: bool = False) -> None:
    assert_no_download_leaks(text)
    assert "סיסמת הגישה" in text
    assert 'class="btn"' not in text
    assert "מזהה המחשב" not in text
    assert "__NEXT__" not in text and "__ERROR__" not in text
    if error:
        assert "סיסמה שגויה" in text
    else:
        assert "סיסמה שגויה" not in text


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def _wait_health(port: int) -> None:
    timeout = aiohttp.ClientTimeout(total=1)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        for _ in range(50):
            try:
                async with http.get(f"http://127.0.0.1:{port}/health") as resp:
                    if resp.status == 200 and (await resp.json()).get("ok") is True:
                        return
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                await asyncio.sleep(0.1)
    raise AssertionError(f"server on {port} did not become healthy")


async def _check_server_process(password: str | None) -> None:
    """The real `python server.py` process, not only the imported app."""
    port = _free_port()
    env = os.environ.copy()
    if password:
        env["SITE_PASSWORD"] = password
    else:
        env.pop("SITE_PASSWORD", None)
    log_path = Path(tempfile.mkstemp(prefix="relay-smoke-", suffix=".log")[1])
    log_file = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).parent / "server.py"), "--port", str(port)],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    try:
        await _wait_health(port)
        async with aiohttp.ClientSession() as http:
            base = f"http://127.0.0.1:{port}"
            async with http.get(base + "/") as resp:
                assert resp.status == 200
                assert_login_page(await resp.text())
            async with http.get(base + "/health") as resp:
                assert resp.status == 200
                assert (await resp.json())["ok"] is True
            async with http.get(base + "/download/support") as resp:
                assert resp.status == 401
                assert_no_download_leaks(await resp.text())
            async with http.get(base + "/download/control") as resp:
                assert resp.status == 401
            if password:
                async with http.post(
                    base + "/login",
                    data={"password": password, "next": "/"},
                    allow_redirects=False,
                ) as resp:
                    assert resp.status == 302, resp.status
                    cookie = resp.cookies[COOKIE_NAME].value
                    assert password not in resp.headers.get("Set-Cookie", "")
                async with http.get(base + "/", headers={"Cookie": f"{COOKIE_NAME}={cookie}"}) as resp:
                    text = await resp.text()
                    assert resp.status == 200
                    assert 'href="/download/support"' in text
                    assert 'href="/download/control"' in text
                    assert "github.com" not in text.lower()
            else:
                async with http.post(
                    base + "/login",
                    data={"password": "anything", "next": "/"},
                    allow_redirects=False,
                ) as resp:
                    assert resp.status == 401
                    assert_login_page(await resp.text(), error=True)
    except Exception as exc:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        if not log_file.closed:
            log_file.close()
        details = log_path.read_text(encoding="utf-8", errors="replace")
        if password:
            details = details.replace(password, "***")
        raise AssertionError(f"{exc}\n--- server log ---\n{details[-2000:]}") from exc
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        if not log_file.closed:
            log_file.close()
        log_path.unlink(missing_ok=True)


async def check_site_gate() -> None:
    hits = {"blob": 0}

    async def latest(request):
        raise aiohttp.web.HTTPFound(f"/blob/{request.match_info['name']}")

    async def blob(request):
        hits["blob"] += 1
        name = request.match_info["name"]
        return aiohttp.web.Response(body=b"MZ-fake-" + name.encode())

    upstream = aiohttp.web.Application()
    upstream.router.add_get("/latest/{name}", latest)
    upstream.router.add_get("/blob/{name}", blob)

    async with TestClient(TestServer(upstream)) as up:
        app = build_app(
            site_password=SITE_PASSWORD,
            download_urls={
                "support": str(up.make_url("/latest/RemoteSupport.exe")),
                "control": str(up.make_url("/latest/RemoteControl.exe")),
            },
        )
        async with TestClient(TestServer(app)) as client:
            health = await client.get("/health")
            assert health.status == 200
            assert (await health.json())["ok"] is True

            home = await client.get("/")
            assert home.status == 200
            home_text = await home.text()
            assert_login_page(home_text)
            assert 'value="/"' in home_text

            viewer = await client.get("/viewer?id=42")
            viewer_text = await viewer.text()
            assert_login_page(viewer_text)
            assert 'value="/viewer?id=42"' in viewer_text

            static = await client.get("/static/index.html")
            assert static.status == 404
            assert_no_download_leaks(await static.text())

            for path in ("/download/support", "/download/control"):
                denied = await client.get(path)
                assert denied.status == 401
                assert_no_download_leaks(await denied.text())
            assert hits["blob"] == 0

            leaked = (
                "https://github.com/nadavi256/KONIMBEZOLBOT/releases/latest/download/RemoteSupport.exe"
            )
            bad = await client.post(
                "/login",
                data={"password": leaked, "next": "/viewer?id=42"},
                allow_redirects=False,
            )
            assert bad.status == 401
            assert_login_page(await bad.text(), error=True)
            assert COOKIE_NAME not in bad.cookies

            async with client.ws_connect("/ws/host") as ws:
                await ws.send_json({"type": "register", "id": "123456", "secret": "abc", "name": "gate"})
                msg = await ws.receive_json(timeout=5)
                assert msg["type"] == "registered", msg

            async with client.ws_connect("/ws/viewer") as ws:
                await ws.send_json({"id": "000000", "password": "not-a-host"})
                msg = await ws.receive_json(timeout=5)
                assert msg["type"] == "error", msg

            good = await client.post(
                "/login",
                data={"password": SITE_PASSWORD, "next": "/viewer?id=42"},
                allow_redirects=False,
            )
            assert good.status == 302
            loc = urlparse(good.headers["Location"])
            assert loc.path == "/viewer" and loc.query == "id=42"
            set_cookie = good.headers["Set-Cookie"]
            assert SITE_PASSWORD not in set_cookie
            folded = set_cookie.lower()
            assert "httponly" in folded
            assert "samesite=lax" in folded
            assert "secure" not in folded
            assert "max-age=" in folded

            page = await client.get("/")
            text = await page.text()
            assert page.status == 200
            assert 'href="/download/support"' in text
            assert 'href="/download/control"' in text
            assert "הורדת תוכנת התמיכה" in text
            assert "הורדת תוכנת השליטה" in text
            assert 'href="/viewer"' in text
            assert "צריכים תמיכה?" in text
            assert "github.com" not in text.lower()
            assert "RemoteSupport.exe" not in text

            viewer_ok = await client.get("/viewer?id=42")
            viewer_body = await viewer_ok.text()
            assert "מזהה המחשב" in viewer_body
            assert "github.com" not in viewer_body.lower()

            support = await client.get("/download/support")
            assert support.status == 200
            assert await support.read() == b"MZ-fake-RemoteSupport.exe"
            assert "RemoteSupport.exe" in support.headers["Content-Disposition"]
            control = await client.get("/download/control")
            assert control.status == 200
            assert await control.read() == b"MZ-fake-RemoteControl.exe"
            assert "RemoteControl.exe" in control.headers["Content-Disposition"]
            assert hits["blob"] == 2

            for bad_next in (
                "https://evil.example/phish",
                "//evil.example/phish",
                "/\\evil.example",
                "http://evil.example",
            ):
                redir = await client.post(
                    "/login",
                    data={"password": SITE_PASSWORD, "next": bad_next},
                    allow_redirects=False,
                )
                assert redir.status == 302
                assert "evil.example" not in redir.headers["Location"]
                assert urlparse(redir.headers["Location"]).path == "/"

            secure = await client.post(
                "/login",
                data={"password": SITE_PASSWORD, "next": "/"},
                headers={"X-Forwarded-Proto": "https"},
                allow_redirects=False,
            )
            assert "secure" in secure.headers["Set-Cookie"].lower()
            assert "httponly" in secure.headers["Set-Cookie"].lower()

            client.session.cookie_jar.clear()
            expired = make_token(SITE_PASSWORD, now=time.time() - COOKIE_MAX_AGE - 60)
            stale = await client.get("/", headers={"Cookie": f"{COOKIE_NAME}={expired}"})
            assert_login_page(await stale.text())
            minted = make_token(SITE_PASSWORD)
            forged = minted[:-1] + ("0" if minted[-1] != "0" else "1")
            tampered = await client.get("/", headers={"Cookie": f"{COOKIE_NAME}={forged}"})
            assert_login_page(await tampered.text())

    saved = os.environ.pop("SITE_PASSWORD", None)
    try:
        assert build_app(site_password="   ")["site_password"] == ""
        closed = build_app()
        assert closed["site_password"] == ""
        async with TestClient(TestServer(closed)) as client:
            health = await client.get("/health")
            assert health.status == 200
            assert (await health.json())["ok"] is True
            assert_login_page(await (await client.get("/")).text())
            assert_login_page(await (await client.get("/viewer")).text())
            denied_login = await client.post(
                "/login",
                data={"password": SITE_PASSWORD, "next": "/"},
                allow_redirects=False,
            )
            assert denied_login.status == 401
            assert_login_page(await denied_login.text(), error=True)
            empty_login = await client.post(
                "/login",
                data={"password": "", "next": "/"},
                allow_redirects=False,
            )
            assert empty_login.status == 401
            for path in ("/download/support", "/download/control"):
                denied = await client.get(path)
                assert denied.status == 401
                assert_no_download_leaks(await denied.text())
            async with client.ws_connect("/ws/host") as ws:
                await ws.send_json({"type": "register", "id": "654321", "secret": "abc", "name": "closed"})
                msg = await ws.receive_json(timeout=5)
                assert msg["type"] == "registered", msg
            async with client.ws_connect("/ws/viewer") as ws:
                await ws.send_json({"id": "000000", "password": "x"})
                msg = await ws.receive_json(timeout=5)
                assert msg["type"] == "error", msg
    finally:
        if saved is not None:
            os.environ["SITE_PASSWORD"] = saved

    await _check_server_process(SITE_PASSWORD)
    await _check_server_process(None)
    print("SITE GATE PASSED")


def cursor_pos():
    import ctypes
    from ctypes import wintypes
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


async def run(host_exe: str) -> None:
    await check_site_gate()
    here = Path(__file__).parent
    # The website password is on, and the installed agent still registers without it.
    env = os.environ.copy()
    env["SITE_PASSWORD"] = SITE_PASSWORD
    server = subprocess.Popen(
        [sys.executable, str(here / "server.py"), "--port", str(PORT)],
        env=env,
    )
    time.sleep(2)
    host = subprocess.Popen([host_exe, "--server", f"http://127.0.0.1:{PORT}", "--console",
                             "--password", PASSWORD, "--no-confirm"])
    try:
        id_file = Path.home() / ".remote_desktop_host.json"
        for _ in range(60):
            if id_file.exists():
                break
            await asyncio.sleep(0.5)
        host_id = json.loads(id_file.read_text())["id"]
        print("host id:", host_id)
        await asyncio.sleep(3)  # let it register

        async with aiohttp.ClientSession() as http:
            async with http.ws_connect(f"ws://127.0.0.1:{PORT}/ws/viewer") as ws:
                await ws.send_json({"id": host_id, "password": "wrong-password"})
                msg = await ws.receive_json(timeout=20)
                assert msg["type"] == "waiting", msg
                msg = await ws.receive_json(timeout=20)
                assert msg["type"] == "error", msg
                print("wrong password rejected: OK")

            async with http.ws_connect(f"ws://127.0.0.1:{PORT}/ws/viewer") as ws:
                await ws.send_json({"id": host_id, "password": PASSWORD})
                got = {}
                deadline = time.time() + 30
                while time.time() < deadline and not ("frame" in got and "screen_info" in got):
                    m = await ws.receive(timeout=30)
                    if m.type == aiohttp.WSMsgType.BINARY:
                        assert m.data[:2] == b"\xff\xd8", "frame is not a JPEG"
                        got["frame"] = len(m.data)
                        await ws.send_json({"type": "ack"})
                    elif m.type == aiohttp.WSMsgType.TEXT:
                        d = json.loads(m.data)
                        got[d["type"]] = d
                        assert d["type"] != "error", d
                print("screen:", got["screen_info"], "first frame bytes:", got["frame"])

                info = got["screen_info"]
                await ws.send_json({"type": "mouse_move", "x": 0.25, "y": 0.5})
                await asyncio.sleep(1.5)
                x, y = cursor_pos()
                print("cursor now at", (x, y))
                assert abs(x - info["width"] * 0.25) < 30 and abs(y - info["height"] * 0.5) < 30, "mouse did not move"
                print("remote mouse control: OK")
        print("SMOKE TEST PASSED")
    finally:
        host.kill()
        server.kill()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(run(sys.argv[1]))
    else:
        asyncio.run(check_site_gate())
