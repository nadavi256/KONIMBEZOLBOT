import json
import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SENT_FILE = Path(__file__).parent / "sent_urls.json"
GH_PAT = os.environ.get("GH_PAT", "")
REPO = "nadavi256/KONIMBEZOLBOT"


def load_sent() -> set:
    if SENT_FILE.exists():
        try:
            return set(json.loads(SENT_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def save_sent(sent: set) -> None:
    SENT_FILE.write_text(json.dumps(sorted(sent), indent=2, ensure_ascii=False), encoding="utf-8")
    _push_sent_file()


def _push_sent_file() -> None:
    if not GH_PAT:
        logger.warning("GH_PAT not set — skipping sent_urls.json push")
        return
    try:
        env = {**os.environ, "GIT_AUTHOR_NAME": "bot", "GIT_AUTHOR_EMAIL": "bot@bot.com",
               "GIT_COMMITTER_NAME": "bot", "GIT_COMMITTER_EMAIL": "bot@bot.com"}
        remote = f"https://x-access-token:{GH_PAT}@github.com/{REPO}.git"
        subprocess.run(["git", "pull", "--rebase", remote, "main"], check=False, capture_output=True, env=env)
        subprocess.run(["git", "add", "sent_urls.json"], check=True, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", "chore: update sent products list"],
            capture_output=True, env=env
        )
        if result.returncode == 0:
            for attempt in range(4):
                r = subprocess.run(["git", "push", remote, "main"], capture_output=True, env=env)
                if r.returncode == 0:
                    logger.info("sent_urls.json pushed to GitHub")
                    return
                wait = 2 ** attempt * 2
                logger.warning(f"Push failed (attempt {attempt+1}/4), retrying in {wait}s")
                time.sleep(wait)
        else:
            logger.info("Nothing new to commit in sent_urls.json")
    except Exception as e:
        logger.error(f"Failed to push sent_urls.json: {e}")
