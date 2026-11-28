"""Simple JSON-file storage for the personal coach: profile memory, logs,
reminders and recent chat history. One file, one owner — no database needed."""
import json
import os
import threading
import uuid
from datetime import datetime, timedelta

DATA_DIR = os.environ.get("COACH_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
STATE_FILE = os.path.join(DATA_DIR, "coach_state.json")
MAX_HISTORY = 30  # last N text turns kept as conversation context

_lock = threading.Lock()
_EMPTY = {"profile": {}, "logs": [], "reminders": [], "history": []}


def _load() -> dict:
    if not os.path.exists(STATE_FILE):
        return json.loads(json.dumps(_EMPTY))
    with open(STATE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    for k, v in _EMPTY.items():
        data.setdefault(k, type(v)())
    return data


def _save(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


# ---------- profile / long-term memory ----------
def get_profile() -> dict:
    with _lock:
        return _load()["profile"]


def save_memory(key: str, value: str) -> None:
    with _lock:
        data = _load()
        if value:
            data["profile"][key] = value
        else:
            data["profile"].pop(key, None)
        _save(data)


# ---------- logs (workouts, meals, weight, sleep...) ----------
def add_log(kind: str, details: str, value: float | None, when: datetime) -> dict:
    entry = {"ts": when.isoformat(timespec="minutes"), "kind": kind, "details": details}
    if value is not None:
        entry["value"] = value
    with _lock:
        data = _load()
        data["logs"].append(entry)
        _save(data)
    return entry


def get_logs(days: int, kind: str | None, now: datetime) -> list[dict]:
    since = (now - timedelta(days=days)).isoformat()
    with _lock:
        logs = _load()["logs"]
    return [l for l in logs if l["ts"] >= since and (not kind or l["kind"] == kind)]


# ---------- reminders ----------
def add_reminder(when: datetime, text: str) -> dict:
    r = {"id": uuid.uuid4().hex[:6], "when": when.isoformat(timespec="minutes"), "text": text}
    with _lock:
        data = _load()
        data["reminders"].append(r)
        _save(data)
    return r


def list_reminders() -> list[dict]:
    with _lock:
        return sorted(_load()["reminders"], key=lambda r: r["when"])


def remove_reminder(rid: str) -> bool:
    with _lock:
        data = _load()
        before = len(data["reminders"])
        data["reminders"] = [r for r in data["reminders"] if r["id"] != rid]
        _save(data)
        return len(data["reminders"]) < before


# ---------- chat history (text only) ----------
def get_history() -> list[dict]:
    with _lock:
        return _load()["history"]


def append_history(user_text: str, assistant_text: str) -> None:
    with _lock:
        data = _load()
        data["history"].append({"role": "user", "content": user_text})
        data["history"].append({"role": "assistant", "content": assistant_text})
        data["history"] = data["history"][-MAX_HISTORY * 2:]
        _save(data)


def clear_history() -> None:
    with _lock:
        data = _load()
        data["history"] = []
        _save(data)
