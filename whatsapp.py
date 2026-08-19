import logging
import os
import random
import time
from typing import Callable

import requests

logger = logging.getLogger(__name__)

# Minimum/maximum pause between sends to different groups, in seconds.
# Sending the same content to several groups back-to-back is the single
# clearest spam signal WhatsApp's anti-abuse systems look for — spacing
# sends out and varying the wording (see build_text) makes each send look
# like an independent human action instead of a broadcast fan-out.
MIN_GROUP_DELAY = 45
MAX_GROUP_DELAY = 180

INSTANCE_ID = os.environ.get("WHATSAPP_INSTANCE_ID", "")
API_TOKEN   = os.environ.get("WHATSAPP_API_TOKEN", "")
BASE_URL    = f"https://api.green-api.com/waInstance{INSTANCE_ID}"

# Comma-separated group chat IDs, e.g. "972501234567-1234567890@g.us,972501234567-0987654321@g.us"
_raw_ids = os.environ.get("WHATSAPP_GROUP_IDS", "")
GROUP_IDS = [g.strip() for g in _raw_ids.split(",") if g.strip()]


def is_configured() -> bool:
    return bool(INSTANCE_ID and API_TOKEN and GROUP_IDS)


def send_to_group(chat_id: str, text: str) -> bool:
    if not is_configured():
        return False
    url = f"{BASE_URL}/sendMessage/{API_TOKEN}"
    try:
        r = requests.post(url, json={"chatId": chat_id, "message": text}, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"WhatsApp send failed to {chat_id}: {e}")
        return False


def send_image_to_group(chat_id: str, image_url: str, caption: str) -> bool:
    if not is_configured():
        return False
    url = f"{BASE_URL}/sendFileByUrl/{API_TOKEN}"
    try:
        r = requests.post(
            url,
            json={"chatId": chat_id, "urlFile": image_url, "fileName": "deal.jpg", "caption": caption},
            timeout=20,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"WhatsApp image send failed to {chat_id}: {e}")
        return False


def send_to_all_groups(build_message: Callable[[], tuple[str, str | None]]) -> int:
    """Send a message to all configured groups, paced like a human sender.

    `build_message` is called once per group and returns (text, image_url) —
    called fresh per group so each one gets an independently-generated
    message instead of one identical string broadcast to all of them.
    Groups are shuffled and separated by a randomized delay so the run
    doesn't look like a synchronized blast. When an image URL is given, it's
    sent as a photo with the text as caption (falling back to text-only if
    the image send fails). Returns count of successes.
    """
    if not is_configured():
        logger.warning("WhatsApp not configured — skipping")
        return 0
    groups = GROUP_IDS.copy()
    random.shuffle(groups)
    success = 0
    for i, gid in enumerate(groups):
        text, image_url = build_message()
        ok = send_image_to_group(gid, image_url, text) if image_url else False
        if not ok:
            ok = send_to_group(gid, text)
        if ok:
            logger.info(f"✅ WhatsApp sent to {gid}")
            success += 1
        else:
            logger.warning(f"❌ WhatsApp failed for {gid}")
        if i < len(groups) - 1:
            delay = random.randint(MIN_GROUP_DELAY, MAX_GROUP_DELAY)
            logger.info(f"Pacing: waiting {delay}s before next group…")
            time.sleep(delay)
    return success
