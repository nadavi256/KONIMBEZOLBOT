import base64
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

GH_PAT = os.environ.get("GH_PAT", "")
REPO = "nadavi256/KONIMBEZOLBOT"
FILE_PATH = "sent_urls.json"
API_URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
HEADERS = {
    "Authorization": f"token {GH_PAT}",
    "Accept": "application/vnd.github.v3+json",
}
# Keep only the last N sent URLs — products can repeat after this window
ROLLING_WINDOW = 75


def load_sent() -> tuple[set, list]:
    """Returns (set of sent URLs, ordered list for rolling window)."""
    if not GH_PAT:
        logger.warning("GH_PAT not set — cannot load sent list")
        return set(), []
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        if r.status_code == 404:
            return set(), []
        r.raise_for_status()
        content = base64.b64decode(r.json()["content"]).decode("utf-8")
        data = json.loads(content)
        logger.info(f"Loaded {len(data)} sent URLs from GitHub")
        return set(data), list(data)
    except Exception as e:
        logger.error(f"Failed to load sent_urls.json: {e}")
        return set(), []


def save_sent(ordered: list) -> None:
    """Save the rolling window list (newest last)."""
    if not GH_PAT:
        logger.warning("GH_PAT not set — cannot save sent list")
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
            "message": "chore: update sent products list",
            "content": content_b64,
            "committer": {"name": "bot", "email": "bot@bot.com"},
        }
        if sha:
            payload["sha"] = sha

        r2 = requests.put(API_URL, headers=HEADERS, json=payload, timeout=15)
        r2.raise_for_status()
        logger.info(f"Saved {len(trimmed)} sent URLs (window={ROLLING_WINDOW})")
    except Exception as e:
        logger.error(f"Failed to save sent_urls.json: {e}")
