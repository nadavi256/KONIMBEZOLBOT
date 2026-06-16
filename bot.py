import asyncio
import logging
import os
import random
import sys
from datetime import datetime
import pytz

import requests
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scraper import get_products
from message_builder import build_message, build_daily_footer
from sent_tracker import load_sent, save_sent

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
_channel_env = os.environ.get("TELEGRAM_CHANNEL_ID", "-1002004379375")
try:
    CHANNEL_ID = int(_channel_env)
except ValueError:
    CHANNEL_ID = -1002004379375  # fallback to known numeric ID
logger_channel = logging.getLogger(__name__ + ".channel")
# Will be printed at startup
PRODUCTS_PER_HOUR = 1  # 1 product per run × every 15 min × 14 hours = 56/day

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def is_valid_affiliate_link(url: str) -> bool:
    """Return True only if the URL is a real AliExpress affiliate link that resolves (not 404)."""
    if not url:
        return False
    # Must be an affiliate short-link
    if "s.click.aliexpress.com" not in url and "aliexpress.com" not in url:
        return False
    try:
        r = requests.head(url, allow_redirects=True, timeout=10, headers=HEADERS)
        if r.status_code == 404:
            return False
        # Any 2xx or 3xx after following redirects is good
        return r.status_code < 500
    except Exception as e:
        logger.warning(f"Link check failed for {url}: {e}")
        return False


async def send_with_retry(bot: Bot, text: str, image_url: str | None = None) -> bool:
    for attempt in range(4):
        try:
            if image_url:
                try:
                    await bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=image_url,
                        caption=text,
                        parse_mode="HTML",
                    )
                    return True
                except TelegramError:
                    await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
                    return True
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
                return True
        except TelegramError as e:
            wait = 2 ** attempt * 2
            logger.warning(f"Telegram error (attempt {attempt + 1}/4): {e}. Retry in {wait}s…")
            await asyncio.sleep(wait)
    logger.error("Failed to send after 4 attempts")
    return False


async def send_hourly_products():
    # Guard: only send between 09:00–21:59 Israel time
    il_time = datetime.now(pytz.timezone("Asia/Jerusalem"))
    if not (9 <= il_time.hour <= 21):
        logger.info(f"Outside active hours ({il_time.strftime('%H:%M')} IL) – skipping")
        return
    logger.info(f"Using channel ID: {CHANNEL_ID} (type: {type(CHANNEL_ID).__name__})")
    """Scrape products, validate affiliate links, and post to channel."""
    logger.info("=== Hourly send started ===")
    bot = Bot(token=BOT_TOKEN)

    sent_urls, sent_ordered = load_sent()
    logger.info(f"Already sent: {len(sent_urls)} products")

    try:
        # Fetch more than needed so we have extras after filtering
        candidates = await get_products(count=PRODUCTS_PER_HOUR * 8)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return

    # Filter out already-sent products, then validate affiliate links
    valid_products = []
    for p in candidates:
        source_url = p.get("source_url", "")
        if source_url in sent_urls:
            logger.info(f"  ⏭ already sent – skipping: {p['name'][:40]}")
            continue
        link = p.get("aliexpress_link", "")
        if is_valid_affiliate_link(link):
            valid_products.append(p)
            logger.info(f"  ✅ link OK: {link[:60]}")
        else:
            logger.warning(f"  ❌ link INVALID/404 – skipping: {p['name'][:40]}")
        if len(valid_products) >= PRODUCTS_PER_HOUR:
            break

    if not valid_products:
        logger.error("No new unsent products after filtering – aborting")
        return

    count = len(valid_products)
    logger.info(f"Sending {count} new products")

    newly_sent = set()
    for i, product in enumerate(valid_products, start=1):
        text = build_message(product, i, count)
        ok = await send_with_retry(bot, text, product.get("image_url"))
        logger.info(f"{'✅' if ok else '❌'} [{i}/{count}] {product['name'][:55]}")
        if ok:
            newly_sent.add(product["source_url"])
        if i < count:
            await asyncio.sleep(random.randint(3, 7))

    # Persist sent URLs (rolling window — append new ones)
    save_sent(sent_ordered + sorted(newly_sent))
    logger.info("=== Hourly send complete ===")


async def main():
    logger.info("Bot starting…")
    async with Bot(token=BOT_TOKEN) as bot:
        me = await bot.get_me()
        logger.info(f"Logged in as {me.full_name} (@{me.username})")

    scheduler = AsyncIOScheduler(timezone="Asia/Jerusalem")

    # Every hour on the hour, 09:00–22:00 Israel time
    scheduler.add_job(
        send_hourly_products,
        trigger="cron",
        hour="9-22",
        minute=0,
        id="hourly_products",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduled: every hour 09:00–22:00 (Asia/Jerusalem)")
    logger.info(f"Channel ID: {CHANNEL_ID}")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "send-now":
        asyncio.run(send_hourly_products())
    else:
        asyncio.run(main())
