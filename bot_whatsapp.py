import asyncio
import logging
import os
import sys
from datetime import datetime
import pytz

from dotenv import load_dotenv

from scraper import get_products
from message_builder import build_whatsapp_message
from whatsapp import send_to_all_groups, is_configured, GROUP_IDS
from whatsapp_tracker import load_wa_sent, save_wa_sent
from known_tracker import load_seen_ever

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

IL_TZ = pytz.timezone("Asia/Jerusalem")
PRODUCTS_PER_RUN = 1


async def send_whatsapp_products():
    il_time = datetime.now(IL_TZ)
    if not (9 <= il_time.hour <= 21):
        logger.info(f"Outside active hours ({il_time.strftime('%H:%M')} IL) — skipping")
        return

    if not is_configured():
        logger.error("WhatsApp not configured — missing secrets")
        return

    logger.info(f"=== WhatsApp send started | {len(GROUP_IDS)} groups ===")

    sent_urls, sent_ordered = load_wa_sent()
    seen_ever = load_seen_ever()

    try:
        candidates = await get_products(
            count=PRODUCTS_PER_RUN * 6,
            exclude_urls=sent_urls,
            seen_ever=seen_ever,
        )
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return

    valid = [p for p in candidates if p.get("aliexpress_link") and p["source_url"] not in sent_urls]
    if not valid:
        logger.error("No new products found — aborting")
        return

    product = valid[0]
    text = build_whatsapp_message(product)
    ok = send_to_all_groups(text)
    logger.info(f"Sent to {ok}/{len(GROUP_IDS)} WhatsApp groups: {product['name'][:55]}")

    if ok > 0:
        save_wa_sent(sent_ordered + [product["source_url"]])

    logger.info("=== WhatsApp send complete ===")


if __name__ == "__main__":
    asyncio.run(send_whatsapp_products())
