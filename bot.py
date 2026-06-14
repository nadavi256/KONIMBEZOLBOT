import asyncio
import logging
import os
import random
import time

from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scraper import get_products
from message_builder import build_message, build_daily_header, build_daily_footer

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
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]

# How many products to send per day
PRODUCTS_PER_DAY = 12

# Delay between messages (seconds) - spread over the day
# We send header + 12 products + footer. Spread across ~8 hours morning session.
MESSAGE_INTERVAL_SECONDS = 60 * 25  # 25 minutes between each product


async def send_message_with_retry(bot: Bot, chat_id: str, text: str, image_url: str | None = None) -> bool:
    for attempt in range(3):
        try:
            if image_url:
                try:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=image_url,
                        caption=text,
                        parse_mode="Markdown",
                    )
                    return True
                except TelegramError:
                    # Fall back to text-only if photo fails
                    await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                    return True
            else:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                return True
        except TelegramError as e:
            logger.warning(f"Telegram error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt * 2)
    return False


async def send_daily_products():
    """Main job: scrape products and post them to the channel."""
    logger.info("Starting daily product send job")
    bot = Bot(token=BOT_TOKEN)

    try:
        products = get_products(count=PRODUCTS_PER_DAY)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return

    if not products:
        logger.error("No products to send")
        return

    count = len(products)

    # Send header
    header = build_daily_header(count)
    await send_message_with_retry(bot, CHANNEL_ID, header)
    await asyncio.sleep(3)

    # Send each product
    for i, product in enumerate(products, start=1):
        text = build_message(product, i, count)
        image = product.get("image_url")
        success = await send_message_with_retry(bot, CHANNEL_ID, text, image)
        if success:
            logger.info(f"Sent product {i}/{count}: {product['name']}")
        else:
            logger.error(f"Failed to send product {i}/{count}: {product['name']}")

        if i < count:
            # Small delay between messages to avoid rate limiting
            delay = random.randint(3, 8)
            await asyncio.sleep(delay)

    # Send footer
    await asyncio.sleep(3)
    footer = build_daily_footer()
    await send_message_with_retry(bot, CHANNEL_ID, footer)

    logger.info("Daily product send complete")


async def send_now():
    """Send products immediately (for testing or manual trigger)."""
    await send_daily_products()


async def main():
    logger.info("Bot starting up...")

    scheduler = AsyncIOScheduler(timezone="Asia/Jerusalem")

    # Schedule daily at 09:00 Israel time
    scheduler.add_job(
        send_daily_products,
        trigger="cron",
        hour=9,
        minute=0,
        id="daily_products",
        name="Daily Products Send",
        replace_existing=True,
    )

    # Optional: second batch at 18:00 (evening)
    scheduler.add_job(
        send_daily_products,
        trigger="cron",
        hour=18,
        minute=0,
        id="evening_products",
        name="Evening Products Send",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started. Jobs scheduled at 09:00 and 18:00 Israel time.")
    logger.info(f"Posting to channel: {CHANNEL_ID}")

    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "send-now":
        # python bot.py send-now  → immediate send for testing
        asyncio.run(send_now())
    else:
        asyncio.run(main())
