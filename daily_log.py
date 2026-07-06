import base64
import json
import logging
import os
from datetime import datetime, timedelta
import pytz

import requests

logger = logging.getLogger(__name__)

GH_PAT = os.environ.get("GH_PAT", "")
REPO = "nadavi256/KONIMBEZOLBOT"
FILE_PATH = "daily_sent.json"
API_URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
HEADERS = {
    "Authorization": f"token {GH_PAT}",
    "Accept": "application/vnd.github.v3+json",
}
IL_TZ = pytz.timezone("Asia/Jerusalem")


def _today_il() -> str:
    return datetime.now(IL_TZ).strftime("%Y-%m-%d")


def _get_file() -> tuple[list, str | None]:
    if not GH_PAT:
        return [], None
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        if r.status_code == 404:
            return [], None
        r.raise_for_status()
        data = json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
        sha = r.json().get("sha")
        return data, sha
    except Exception as e:
        logger.error(f"daily_log fetch failed: {e}")
        return [], None


def _save_file(entries: list, sha: str | None) -> None:
    if not GH_PAT:
        return
    try:
        content_b64 = base64.b64encode(
            json.dumps(entries, indent=2, ensure_ascii=False).encode("utf-8")
        ).decode("utf-8")
        payload = {
            "message": "chore: update daily sent log",
            "content": content_b64,
            "committer": {"name": "bot", "email": "bot@bot.com"},
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(API_URL, headers=HEADERS, json=payload, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"daily_log save failed: {e}")


def log_product(product: dict) -> None:
    """Append one product to today's daily log."""
    entries, sha = _get_file()
    today = _today_il()
    # Keep last 30 days of history
    cutoff = (datetime.now(IL_TZ) - timedelta(days=30)).strftime("%Y-%m-%d")
    entries = [e for e in entries if e.get("date", "") >= cutoff]
    entries.append({
        "date": today,
        "time": datetime.now(IL_TZ).strftime("%H:%M"),
        "name": product.get("name", ""),
        "category": product.get("category", ""),
        "url": product.get("source_url", ""),
        "link": product.get("aliexpress_link", ""),
    })
    _save_file(entries, sha)


def load_today() -> list[dict]:
    """Return today's sent products."""
    entries, _ = _get_file()
    today = _today_il()
    return [e for e in entries if e.get("date") == today]


def load_recent_urls(days: int = 2) -> set:
    """Return URLs sent in the last N days — used as a hard dedup barrier."""
    entries, _ = _get_file()
    cutoff = (datetime.now(IL_TZ) - timedelta(days=days)).strftime("%Y-%m-%d")
    return {e["url"] for e in entries if e.get("date", "") >= cutoff and e.get("url")}
