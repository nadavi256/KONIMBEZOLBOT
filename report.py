"""Send daily deal report to Telegram at 23:00 IL."""
import asyncio
import html
import logging
import os
import sys
from datetime import datetime

import pytz
from dotenv import load_dotenv
from telegram import Bot

from daily_log import load_today

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
REPORT_CHAT_ID = os.environ.get("REPORT_CHAT_ID", os.environ.get("TELEGRAM_CHANNEL_ID", ""))
IL_TZ = pytz.timezone("Asia/Jerusalem")

CATEGORY_EMOJIS = {
    "אופנה וסטייל": "👗",
    "מוצרי מטבח": "🍳",
    "מוצרים לרכב": "🚗",
    "ספורט וכושר": "💪",
    "בית וגן": "🏠",
    "שעונים ותכשיטים": "⌚",
    "גאדג'טים": "🔧",
    "כלי עבודה": "🛠️",
    "מוצרים לילדים": "🎁",
}


def build_report_plain(entries: list[dict]) -> str:
    """Plain text version for email."""
    now = datetime.now(IL_TZ).strftime("%d/%m/%Y")

    if not entries:
        return (
            f"דוח יומי — {now}\n\n"
            "לא נשלחו דילים היום.\n"
            "בדוק שה-cron-job.org פעיל ושה-GitHub Actions רצים."
        )

    lines = [f"דוח יומי — {now}", f"נשלחו {len(entries)} דילים היום:", ""]

    by_cat: dict[str, list] = {}
    for entry in entries:
        cat = entry.get("category", "אחר")
        by_cat.setdefault(cat, []).append(entry)

    for cat, items in by_cat.items():
        emoji = CATEGORY_EMOJIS.get(cat, "⭐")
        lines.append(f"{emoji} {cat}")
        for item in items:
            time_str = item.get("time", "")
            name = item.get("name", "")[:60]
            link = item.get("link", "")
            lines.append(f"  {time_str} — {name}")
            if link:
                lines.append(f"           {link}")
        lines.append("")

    total = len(entries)
    if total >= 10:
        lines.append(f"✅ ביצועים מעולים! {total} דילים יצאו היום.")
    elif total >= 5:
        lines.append(f"👍 {total} דילים יצאו היום — תקין.")
    else:
        lines.append(f"⚠️ רק {total} דילים יצאו היום — כדאי לבדוק שהבוט פועל.")

    return "\n".join(lines)


def build_report_html(entries: list[dict]) -> str:
    """HTML version for Telegram."""
    e = html.escape
    now = datetime.now(IL_TZ).strftime("%d/%m/%Y")

    if not entries:
        return (
            f"📊 <b>דוח יומי — {e(now)}</b>\n\n"
            "❌ לא נשלחו דילים היום.\n\n"
            "בדוק שה-cron-job.org פעיל ושה-GitHub Actions רצים."
        )

    lines = [f"📊 <b>דוח יומי — {e(now)}</b>\n", f"נשלחו <b>{len(entries)}</b> דילים היום:\n"]

    by_cat: dict[str, list] = {}
    for entry in entries:
        cat = entry.get("category", "אחר")
        by_cat.setdefault(cat, []).append(entry)

    for cat, items in by_cat.items():
        emoji = CATEGORY_EMOJIS.get(cat, "⭐")
        lines.append(f"\n{emoji} <b>{e(cat)}</b>")
        for item in items:
            time_str = item.get("time", "")
            name = e(item.get("name", "")[:55])
            lines.append(f"  {e(time_str)} — {name}")

    total = len(entries)
    if total >= 10:
        lines.append(f"\n✅ <b>ביצועים מעולים!</b> {total} דילים יצאו היום.")
    elif total >= 5:
        lines.append(f"\n👍 {total} דילים יצאו היום — תקין.")
    else:
        lines.append(f"\n⚠️ רק {total} דילים יצאו היום — כדאי לבדוק שהבוט פועל.")

    return "\n".join(lines)


async def send_report(output_file: str | None = None):
    logger.info("Building daily report…")
    entries = load_today()
    logger.info(f"Found {len(entries)} entries for today")

    plain = build_report_plain(entries)

    # Write plain text for email action
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(plain)
        logger.info(f"Report written to {output_file}")

    # Also send HTML version to Telegram if REPORT_CHAT_ID is set
    if REPORT_CHAT_ID:
        html_text = build_report_html(entries)
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(
            chat_id=int(REPORT_CHAT_ID),
            text=html_text,
            parse_mode="HTML",
        )
        logger.info("Daily report sent to Telegram.")


if __name__ == "__main__":
    out = None
    if "--output-file" in sys.argv:
        idx = sys.argv.index("--output-file")
        out = sys.argv[idx + 1]
    asyncio.run(send_report(output_file=out))

