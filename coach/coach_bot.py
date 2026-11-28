"""Telegram side of the coach (optional). Started by server.py when
COACH_BOT_TOKEN is set. Only answers the owner (OWNER_CHAT_ID)."""
import asyncio
import base64
import logging
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import brain
import storage

logger = logging.getLogger("coach.telegram")

BOT_TOKEN = os.environ.get("COACH_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", "0") or 0)  # 0 = setup mode: bot tells you your id

_app: Application | None = None


def is_configured() -> bool:
    return bool(BOT_TOKEN)


async def send_to_owner(text: str) -> None:
    if not (_app and OWNER_CHAT_ID):
        return
    for i in range(0, len(text), 4000):
        await _app.bot.send_message(chat_id=OWNER_CHAT_ID, text=text[i:i + 4000])


async def _think(user_content, history_text: str) -> str:
    try:
        return await asyncio.to_thread(brain.chat, user_content, history_text)
    except Exception:
        logger.exception("Claude call failed")
        return "יש לי תקלה רגעית בחיבור 😅 נסה שוב עוד דקה."


def _is_owner(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == OWNER_CHAT_ID)


async def on_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not OWNER_CHAT_ID:
        await update.message.reply_text(
            f"ה-Chat ID שלך: {update.effective_chat.id}\n"
            "שים אותו במשתנה OWNER_CHAT_ID והפעל מחדש את השרת.")
        return
    if _is_owner(update):
        await on_text(update, ctx, override="היי! תתחיל להכיר אותי כדי שתוכל לאמן אותי.")


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE, override: str | None = None) -> None:
    if not _is_owner(update):
        return
    text = override or update.message.text
    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
    await send_to_owner(await _think(text, text))


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
    await send_to_owner(await _think(content, f"[תמונה] {caption}"))


async def on_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    p = storage.get_profile()
    text = "\n".join(f"• {k}: {v}" for k, v in p.items()) or "עוד לא שמרתי עליך כלום."
    await send_to_owner("🧠 מה שאני זוכר עליך:\n" + text)


async def on_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    storage.clear_history()
    await update.message.reply_text("ניקיתי את השיחה האחרונה (הפרופיל והרישומים נשמרו).")


async def start() -> None:
    """Start polling Telegram inside the already-running event loop."""
    global _app
    _app = Application.builder().token(BOT_TOKEN).build()
    _app.add_handler(CommandHandler("start", on_start))
    _app.add_handler(CommandHandler("profile", on_profile))
    _app.add_handler(CommandHandler("reset", on_reset))
    _app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    await _app.initialize()
    await _app.start()
    await _app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    if not OWNER_CHAT_ID:
        logger.warning("OWNER_CHAT_ID not set — send /start to the bot to get your id")


async def stop() -> None:
    if _app:
        await _app.updater.stop()
        await _app.stop()
        await _app.shutdown()
