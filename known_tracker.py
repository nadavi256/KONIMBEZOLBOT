"""Track every product URL ever seen in the sitemap.

Unlike sent_tracker (rolling window of 70), this file grows permanently.
Any URL NOT in seen_ever is a genuinely NEW product added to the site.
"""
import base64
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

GH_PAT = os.environ.get("GH_PAT", "")
REPO = "nadavi256/KONIMBEZOLBOT"
FILE_PATH = "seen_ever.json"
API_URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
HEADERS = {
    "Authorization": f"token {GH_PAT}",
    "Accept": "application/vnd.github.v3+json",
}


def load_seen_ever() -> set:
    if not GH_PAT:
        return set()
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        if r.status_code == 404:
            return set()
        r.raise_for_status()
        data = json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
        logger.info(f"Loaded {len(data)} known products from seen_ever.json")
        return set(data)
    except Exception as e:
        logger.error(f"Failed to load seen_ever.json: {e}")
        return set()


def save_seen_ever(urls: set) -> None:
    if not GH_PAT:
        return
    try:
        ordered = sorted(urls)
        content_b64 = base64.b64encode(
            json.dumps(ordered, indent=2, ensure_ascii=False).encode("utf-8")
        ).decode("utf-8")

        sha = None
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha")

        payload = {
            "message": "chore: update known products list",
            "content": content_b64,
            "committer": {"name": "bot", "email": "bot@bot.com"},
        }
        if sha:
            payload["sha"] = sha

        r2 = requests.put(API_URL, headers=HEADERS, json=payload, timeout=15)
        r2.raise_for_status()
        logger.info(f"Saved {len(ordered)} known products to seen_ever.json")
    except Exception as e:
        logger.error(f"Failed to save seen_ever.json: {e}")
