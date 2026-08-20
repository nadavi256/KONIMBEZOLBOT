import asyncio
import logging
import os
import random
import sys
from datetime import datetime
import pytz

from dotenv import load_dotenv

from scraper import get_products
from message_builder import build_whatsapp_message
from whatsapp import send_to_all_groups, is_configured, GROUP_IDS
from whatsapp_tracker import load_wa_sent, save_wa_sent, get_daily_state, record_daily_send, get_or_start_warmup
from whatsapp_warmup import compute_daily_cap, compute_min_gap_minutes
from known_tracker import load_seen_ever
from copywriter import generate_whatsapp_copy
from whatsapp_daily_log import log_product as log_whatsapp_product

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

IL_TZ = pytz.timezone("Asia/Jerusalem")
PRODUCTS_PER_RUN = 1

# Startup jitter: don't fire at the exact same second the workflow trigger
# fired every time — a perfectly regular cadence is itself a bot signature.
STARTUP_JITTER_MAX_SECONDS = 90

# Small tolerance so a run that's a minute or two early (jitter, scraping
# time) doesn't get skipped over a near-miss on the spacing requirement.
GAP_TOLERANCE_MINUTES = 2


async def send_whatsapp_products():
    il_time = datetime.now(IL_TZ)
    if not (9 <= il_time.hour <= 21):
        logger.info(f"Outside active hours ({il_time.strftime('%H:%M')} IL) — skipping")
        return

    if not is_configured():
        logger.error("WhatsApp not configured — missing secrets")
        return

    warmup_start = get_or_start_warmup()
    days_since_start = (il_time.date() - datetime.strptime(warmup_start, "%Y-%m-%d").date()).days
    daily_cap = compute_daily_cap(days_since_start)
    min_gap_minutes = compute_min_gap_minutes(daily_cap)

    state = get_daily_state()
    sent_today, last_sent_at = state["count"], state["last_sent_at"]

    if sent_today >= daily_cap:
        logger.info(f"Daily cap reached ({sent_today}/{daily_cap}, ramp day {days_since_start}) — skipping")
        return

    if last_sent_at:
        minutes_since_last = (il_time - datetime.fromisoformat(last_sent_at)).total_seconds() / 60
        if minutes_since_last < min_gap_minutes - GAP_TOLERANCE_MINUTES:
            logger.info(
                f"Too soon since last send ({minutes_since_last:.0f}m of {min_gap_minutes:.0f}m "
                f"required at today's pace) — skipping"
            )
            return

    jitter = random.randint(0, STARTUP_JITTER_MAX_SECONDS)
    logger.info(f"Startup jitter: waiting {jitter}s…")
    await asyncio.sleep(jitter)

    logger.info(
        f"=== WhatsApp send started | {len(GROUP_IDS)} groups | {sent_today}/{daily_cap} today "
        f"(ramp day {days_since_start}) ==="
    )

    sent_urls, sent_ordered = load_wa_sent()
    seen_ever = load_seen_ever()

    try:
        candidates = await get_products(
            count=PRODUCTS_PER_RUN * 6,
            exclude_urls=sent_urls,
            seen_ever=seen_ever,
            fetch_stats=True,
        )
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return

    valid = [p for p in candidates if p.get("aliexpress_link") and p["source_url"] not in sent_urls]
    if not valid:
        logger.error("No new products found — aborting")
        return

    product = valid[0]
    logger.info(
        f"Product data: price={product.get('price')} rating={product.get('rating')} "
        f"orders={product.get('orders')} image={'yes' if product.get('image_url') else 'no'}"
    )

    copy_source_used = {"value": "template"}

    def build_message() -> tuple[str, str | None]:
        ai_text = generate_whatsapp_copy(product)
        copy_source_used["value"] = "ai" if ai_text else "template"
        logger.info(f"Copy source: {'AI copywriter' if ai_text else 'template fallback'}")
        return ai_text or build_whatsapp_message(product), product.get("image_url")

    ok = send_to_all_groups(build_message)
    logger.info(f"Sent to {ok}/{len(GROUP_IDS)} WhatsApp groups: {product['name'][:55]}")

    if ok > 0:
        save_wa_sent(sent_ordered + [product["source_url"]])
        record_daily_send()
        log_whatsapp_product(product, copy_source_used["value"], ok)

    logger.info("=== WhatsApp send complete ===")


if __name__ == "__main__":
    asyncio.run(send_whatsapp_products())
