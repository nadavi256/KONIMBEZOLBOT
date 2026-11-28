"""Personal coach & assistant — a private Telegram bot powered by Claude.

Only answers the owner (OWNER_CHAT_ID). Sends a morning and evening check-in,
fires reminders, logs workouts/meals/weight, and remembers you over time.
"""
import asyncio
import base64
import logging
import os
from datetime import datetime, time

from dotenv import load_dotenv

load_dotenv()

from telegram import Update  # noqa: E402
from telegram.ext import (  # noqa: E402
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)

import brain  # noqa: E402
import storage  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("coach")

BOT_TOKEN = os.environ["COACH_BOT_TOKEN"]
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", "0"))  # 0 = setup mode: bot tells you your id
MORNING = os.environ.get("COACH_MORNING", "07:30")
EVENING = os.environ.get("COACH_EVENING", "21:00")

_app: Application | None = None


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m), tzinfo=brain.TZ)


async def send_long(chat_id: int, text: str) -> None:
    for i in range(0, len(text), 4000):
        await _app.bot.send_message(chat_id=chat_id, text=text[i:i + 4000])


# ---------- reminders ----------
async def _fire_reminder(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    r = ctx.job.data
    await ctx.bot.send_message(chat_id=OWNER_CHAT_ID, text=f"⏰ תזכורת: {r['text']}")
    storage.remove_reminder(r["id"])


def schedule_reminder(r: dict) -> None:
    when = datetime.fromisoformat(r["when"])
    if when.tzinfo is None:
        when = brain.TZ.localize(when)
    _app.job_queue.run_once(_fire_reminder, when=when, data=r, name=r["id"])


def _schedule_from_thread(r: dict) -> None:
    # brain.chat runs in a worker thread; hop back onto the bot's event loop.
    _loop.call_soon_threadsafe(schedule_reminder, r)


# ---------- talking to Claude ----------
async def _think(user_content, history_text: str) -> str:
    try:
        return await asyncio.to_thread(brain.chat, user_content, history_text, _schedule_from_thread)
    except Exception:
        logger.exception("Claude call failed")
        return "יש לי תקלה רגעית בחיבור 😅 נסה שוב עוד דקה."


def _is_owner(update: Update) -> bool:
    return update.effective_chat and update.effective_chat.id == OWNER_CHAT_ID


async def on_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not OWNER_CHAT_ID:
        await update.message.reply_text(
            f"ה-Chat ID שלך: {update.effective_chat.id}\n"
            "שים אותו במשתנה OWNER_CHAT_ID והפעל מחדש את הבוט.")
        return
    if not _is_owner(update):
        return
    await on_text(update, ctx, override="היי! תתחיל להכיר אותי כדי שתוכל לאמן אותי.")


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE, override: str | None = None) -> None:
    if not _is_owner(update):
        return
    text = override or update.message.text
    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
    reply = await _think(text, text)
    await send_long(update.effective_chat.id, reply)


async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
    f = await update.message.photo[-1].get_file()
    data = bytes(await f.download_as_bytearray())
    caption = update.message.caption or "שלחתי תמונה (כנראה ארוחה / מסך אימון / שקילה)."
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                     "data": base64.standard_b64encode(data).decode()}},
        {"type": "text", "text": caption},
    ]
    reply = await _think(content, f"[תמונה] {caption}")
    await send_long(update.effective_chat.id, reply)


async def on_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    p = storage.get_profile()
    text = "\n".join(f"• {k}: {v}" for k, v in p.items()) or "עוד לא שמרתי עליך כלום."
    await send_long(update.effective_chat.id, "🧠 מה שאני זוכר עליך:\n" + text)


async def on_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    storage.clear_history()
    await update.message.reply_text("ניקיתי את השיחה האחרונה (הפרופיל והרישומים נשמרו).")


# ---------- daily check-ins ----------
async def _checkin(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    kind = ctx.job.data
    prompt = {
        "morning": "[הודעה אוטומטית מהמערכת, לא מהמשתמש] זה צ'ק-אין בוקר. שלח למשתמש הודעת בוקר "
                   "קצרה: מה התוכנית להיום לפי הפרופיל שלו (אימון/מנוחה), יעד אחד קטן ליום, ושאלה אחת.",
        "evening": "[הודעה אוטומטית מהמערכת, לא מהמשתמש] זה צ'ק-אין ערב. בדוק עם get_logs מה נרשם היום, "
                   "ושלח הודעה קצרה: פרגון על מה שנעשה, ושאל על מה שחסר (אימון/אוכל/שתייה/שינה).",
    }[kind]
    reply = await _think(prompt, prompt)
    await send_long(OWNER_CHAT_ID, reply)


async def _post_init(app: Application) -> None:
    global _loop
    _loop = asyncio.get_running_loop()
    if not OWNER_CHAT_ID:
        logger.warning("OWNER_CHAT_ID not set — send /start to the bot to get your id")
        return
    app.job_queue.run_daily(_checkin, _hm(MORNING), data="morning", name="morning")
    app.job_queue.run_daily(_checkin, _hm(EVENING), data="evening", name="evening")
    for r in storage.list_reminders():
        when = datetime.fromisoformat(r["when"])
        if when > brain.now():
            schedule_reminder(r)
        else:
            storage.remove_reminder(r["id"])
    logger.info("Coach ready. Check-ins at %s and %s", MORNING, EVENING)


_loop: asyncio.AbstractEventLoop | None = None


def main() -> None:
    global _app
    _app = Application.builder().token(BOT_TOKEN).post_init(_post_init).build()
    _app.add_handler(CommandHandler("start", on_start))
    _app.add_handler(CommandHandler("profile", on_profile))
    _app.add_handler(CommandHandler("reset", on_reset))
    _app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    _app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
