"""
End-to-end check used by CI on a real Windows machine:
starts the relay server, starts the built RemoteSupport.exe, connects as a
viewer, verifies a screen frame arrives and that the remote mouse moves.

    python smoke_test.py dist/RemoteSupport.exe
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import aiohttp

PORT = 8765
PASSWORD = "smoketest123"


def cursor_pos():
    import ctypes
    from ctypes import wintypes
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


async def run(host_exe: str) -> None:
    here = Path(__file__).parent
    server = subprocess.Popen([sys.executable, str(here / "server.py"), "--port", str(PORT)])
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
    asyncio.run(run(sys.argv[1]))
