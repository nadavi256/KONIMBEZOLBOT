import base64
import json
import logging
import os
from datetime import datetime

import pytz
import requests

logger = logging.getLogger(__name__)

GH_PAT = os.environ.get("GH_PAT", "")
REPO = "nadavi256/KONIMBEZOLBOT"
FILE_PATH = "whatsapp_sent.json"
API_URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
DAILY_FILE_PATH = "whatsapp_daily.json"
DAILY_API_URL = f"https://api.github.com/repos/{REPO}/contents/{DAILY_FILE_PATH}"
HEADERS = {
    "Authorization": f"token {GH_PAT}",
    "Accept": "application/vnd.github.v3+json",
}
ROLLING_WINDOW = 150
IL_TZ = pytz.timezone("Asia/Jerusalem")


def load_wa_sent() -> tuple[set, list]:
    if not GH_PAT:
        return set(), []
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        if r.status_code == 404:
            return set(), []
        r.raise_for_status()
        data = json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
        data = data[-ROLLING_WINDOW:]
        logger.info(f"Loaded {len(data)} WhatsApp sent URLs")
        return set(data), list(data)
    except Exception as e:
        logger.error(f"Failed to load whatsapp_sent.json: {e}")
        return set(), []


def save_wa_sent(ordered: list) -> None:
    if not GH_PAT:
        return
    try:
        trimmed = ordered[-ROLLING_WINDOW:]
        content_b64 = base64.b64encode(
            json.dumps(trimmed, indent=2, ensure_ascii=False).encode("utf-8")
        ).decode("utf-8")
        sha = None
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha")
        payload = {
            "message": "chore: update WhatsApp sent list",
            "content": content_b64,
            "committer": {"name": "bot", "email": "bot@bot.com"},
        }
        if sha:
            payload["sha"] = sha
        r2 = requests.put(API_URL, headers=HEADERS, json=payload, timeout=15)
        r2.raise_for_status()
        logger.info(f"Saved {len(trimmed)} WhatsApp sent URLs")
    except Exception as e:
        logger.error(f"Failed to save whatsapp_sent.json: {e}")


def get_daily_send_count() -> int:
    """How many WhatsApp runs already sent today (Israel time).

    Used as a hard safety cap so a stray extra trigger (manual re-run,
    workflow misfire) can't push the group past a human-like daily volume,
    independent of how often the workflow itself is scheduled.
    """
    if not GH_PAT:
        return 0
    today = datetime.now(IL_TZ).strftime("%Y-%m-%d")
    try:
        r = requests.get(DAILY_API_URL, headers=HEADERS, timeout=10)
        if r.status_code == 404:
            return 0
        r.raise_for_status()
        data = json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
        return data.get("count", 0) if data.get("date") == today else 0
    except Exception as e:
        logger.error(f"Failed to load whatsapp_daily.json: {e}")
        return 0


def record_daily_send() -> None:
    """Increment today's send counter (resets automatically on a new day)."""
    if not GH_PAT:
        return
    today = datetime.now(IL_TZ).strftime("%Y-%m-%d")
    try:
        sha = None
        count = 0
        r = requests.get(DAILY_API_URL, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            body = r.json()
            sha = body.get("sha")
            existing = json.loads(base64.b64decode(body["content"]).decode("utf-8"))
            if existing.get("date") == today:
                count = existing.get("count", 0)

        content_b64 = base64.b64encode(
            json.dumps({"date": today, "count": count + 1}, ensure_ascii=False).encode("utf-8")
        ).decode("utf-8")
        payload = {
            "message": "chore: update WhatsApp daily send count",
            "content": content_b64,
            "committer": {"name": "bot", "email": "bot@bot.com"},
        }
        if sha:
            payload["sha"] = sha
        r2 = requests.put(DAILY_API_URL, headers=HEADERS, json=payload, timeout=15)
        r2.raise_for_status()
        logger.info(f"WhatsApp daily send count: {count + 1}")
    except Exception as e:
        logger.error(f"Failed to save whatsapp_daily.json: {e}")
