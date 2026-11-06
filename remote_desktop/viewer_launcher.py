"""
RemoteControl.exe - the technician's app.

Opens the viewer page of your relay server in its own app window
(Microsoft Edge "app mode", built into every Windows 10/11),
so it looks and behaves like a normal desktop program.
"""

import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def server_url() -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    try:
        url = json.loads((base / "config.json").read_text(encoding="utf-8")).get("server_url", "")
    except (OSError, ValueError):
        url = ""
    return url.strip().rstrip("/")


def find_edge() -> str | None:
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        root = os.environ.get(env)
        if root:
            exe = Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if exe.exists():
                return str(exe)
    return None


def main() -> None:
    base = server_url()
    if not base:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "לא הוגדרה כתובת שרת בתוכנה.", "שליטה מרחוק", 0x10)
        return
    url = base + "/viewer"
    edge = find_edge()
    if edge:
        # separate profile so the window opens as its own app, maximized
        profile = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "RemoteControlViewer"
        subprocess.Popen([edge, f"--app={url}", "--start-maximized", "--no-first-run",
                          f"--user-data-dir={profile}"])
    else:
        webbrowser.open(url)


if __name__ == "__main__":
    main()
