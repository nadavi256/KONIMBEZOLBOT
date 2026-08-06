import logging
import os
import requests

logger = logging.getLogger(__name__)

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


def send_to_all_groups(text: str) -> int:
    """Send message to all configured groups. Returns count of successes."""
    if not is_configured():
        logger.warning("WhatsApp not configured — skipping")
        return 0
    success = 0
    for gid in GROUP_IDS:
        if send_to_group(gid, text):
            logger.info(f"✅ WhatsApp sent to {gid}")
            success += 1
        else:
            logger.warning(f"❌ WhatsApp failed for {gid}")
    return success
