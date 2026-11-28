"""Coach server — the brain behind the watch (and the optional Telegram bot).

Watch API (every request carries header X-Device-Key and ?steps=&batt=):
  POST /device/talk            body: raw PCM s16le 16kHz mono -> {"id", "pages", "text"}
  GET  /device/inbox           -> {"id", "pages"} when the coach has something to say, else {}
  GET  /device/home            -> 240x240 RGB565 home screen (clock, steps ring)
  GET  /device/screen/{id}/{n} -> 240x240 RGB565 page n of a reply
  GET  /device/audio/{id}      -> raw PCM s16le 16kHz mono speech of a reply
  GET  /health                 -> "ok"
"""
import asyncio
import hmac
import logging
import os
import time
import uuid
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from aiohttp import web  # noqa: E402

import brain  # noqa: E402
import coach_bot  # noqa: E402
import screens  # noqa: E402
import storage  # noqa: E402
import voice  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("coach.server")

DEVICE_KEY = os.environ.get("DEVICE_KEY", "")
PORT = int(os.environ.get("PORT", "8080"))
STEP_GOAL = int(os.environ.get("DAILY_STEP_GOAL", "8000"))
MORNING = os.environ.get("COACH_MORNING", "07:30")
EVENING = os.environ.get("COACH_EVENING", "21:00")

# Replies rendered for the watch, kept in memory for a while.
_replies: dict[str, dict] = {}
REPLY_TTL = 30 * 60


def _new_reply(text: str) -> dict:
    now = time.time()
    for k in [k for k, v in _replies.items() if now - v["t"] > REPLY_TTL]:
        del _replies[k]
    rid = uuid.uuid4().hex[:10]
    r = {"t": now, "text": text, "pages": screens.reply_pages(text), "audio": None}
    _replies[rid] = r
    return {"id": rid, "pages": len(r["pages"]), "text": text}


# ---------------------------------------------------------------- helpers
def _auth(req: web.Request) -> None:
    if not DEVICE_KEY or not hmac.compare_digest(req.headers.get("X-Device-Key", ""), DEVICE_KEY):
        raise web.HTTPUnauthorized()


def _sync(req: web.Request) -> tuple[int, int | None]:
    """Every watch request reports its pedometer and battery; record them."""
    try:
        raw = int(req.query.get("steps", ""))
        today = storage.update_steps(raw, brain.now().strftime("%Y-%m-%d"))
    except ValueError:
        today = storage.get_steps().get(brain.now().strftime("%Y-%m-%d"), 0)
    try:
        batt = int(req.query.get("batt", ""))
    except ValueError:
        batt = None
    return today, batt


# ---------------------------------------------------------------- watch API
async def talk(req: web.Request) -> web.Response:
    _auth(req)
    _sync(req)
    pcm = await req.read()
    if len(pcm) < 16000:  # < 0.5s
        return web.json_response({"error": "too short"}, status=400)
    try:
        heard = await asyncio.to_thread(voice.transcribe, pcm)
    except Exception:
        logger.exception("speech-to-text failed")
        return web.json_response(_new_reply("לא הצלחתי לשמוע. נסה שוב?"))
    logger.info("heard: %s", heard)
    if not heard:
        return web.json_response(_new_reply("לא שמעתי כלום, נסה לדבר קרוב יותר לשעון."))
    try:
        answer = await asyncio.to_thread(brain.chat, heard, f"[בקול מהשעון] {heard}",
                                         lambda r: None, "watch")
    except Exception:
        logger.exception("Claude call failed")
        answer = "יש לי תקלה רגעית בחיבור. נסה שוב עוד דקה."
    return web.json_response(_new_reply(answer))


async def inbox(req: web.Request) -> web.Response:
    _auth(req)
    _sync(req)
    text = storage.pop_outbox()
    if not text:
        return web.json_response({})
    r = _new_reply(text)
    return web.json_response({"id": r["id"], "pages": r["pages"]})


async def home(req: web.Request) -> web.Response:
    _auth(req)
    today, batt = _sync(req)
    img = screens.home(brain.now(), today, STEP_GOAL, batt)
    return web.Response(body=img, content_type="application/octet-stream")


async def screen(req: web.Request) -> web.Response:
    _auth(req)
    r = _replies.get(req.match_info["rid"])
    n = int(req.match_info["page"])
    if not r or not 0 <= n < len(r["pages"]):
        raise web.HTTPNotFound()
    return web.Response(body=r["pages"][n], content_type="application/octet-stream")


async def audio(req: web.Request) -> web.Response:
    _auth(req)
    r = _replies.get(req.match_info["rid"])
    if not r:
        raise web.HTTPNotFound()
    if r["audio"] is None:
        if not voice.is_configured():
            r["audio"] = b""
        else:
            try:
                r["audio"] = await asyncio.to_thread(voice.speak, r["text"])
            except Exception:
                logger.exception("text-to-speech failed")
                r["audio"] = b""
    return web.Response(body=r["audio"], content_type="application/octet-stream")


async def health(_req: web.Request) -> web.Response:
    return web.Response(text="ok")


# ---------------------------------------------------------------- scheduler
CHECKIN_PROMPTS = {
    "morning": "[הודעה אוטומטית מהמערכת, לא מהמשתמש] צ'ק-אין בוקר. שלח למשתמש הודעת בוקר קצרה: "
               "מה התוכנית להיום לפי הפרופיל שלו (אימון/מנוחה), יעד אחד קטן ליום, ושאלה אחת.",
    "evening": "[הודעה אוטומטית מהמערכת, לא מהמשתמש] צ'ק-אין ערב. בדוק עם get_logs מה נרשם היום ומה מספר "
               "הצעדים, ושלח הודעה קצרה: פרגון על מה שנעשה, ושאל על מה שחסר (אימון/אוכל/שתייה/שינה).",
}


async def _deliver(text: str) -> None:
    """Send a proactive message to the watch (vibrates + speaks) and Telegram."""
    storage.push_outbox(text)
    try:
        await coach_bot.send_to_owner(text)
    except Exception:
        logger.exception("telegram send failed")


async def scheduler() -> None:
    while True:
        try:
            n = brain.now()
            for r in storage.list_reminders():
                if datetime.fromisoformat(r["when"]) <= n:
                    storage.remove_reminder(r["id"])
                    await _deliver(f"תזכורת: {r['text']}")
            today = n.strftime("%Y-%m-%d")
            for kind, hhmm in (("morning", MORNING), ("evening", EVENING)):
                late = _minutes(n.strftime("%H:%M")) - _minutes(hhmm)
                if late >= 0 and storage.get_meta(f"checkin_{kind}") != today:
                    storage.set_meta(f"checkin_{kind}", today)
                    if late > 60:
                        continue  # server was down at check-in time; skip a stale check-in
                    p = CHECKIN_PROMPTS[kind]
                    text = await asyncio.to_thread(brain.chat, p, p, lambda r: None, "watch")
                    await _deliver(text)
        except Exception:
            logger.exception("scheduler tick failed")
        await asyncio.sleep(30)


def _minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


# ---------------------------------------------------------------- main
async def _on_startup(app: web.Application) -> None:
    if not DEVICE_KEY:
        logger.warning("DEVICE_KEY is not set — the watch API will reject every request")
    if not voice.is_configured():
        logger.warning("ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not set — the watch can't hear or speak")
    if coach_bot.is_configured():
        await coach_bot.start()
    app["scheduler"] = asyncio.create_task(scheduler())
    logger.info("Coach server on :%d (check-ins %s / %s)", PORT, MORNING, EVENING)


async def _on_cleanup(app: web.Application) -> None:
    app["scheduler"].cancel()
    await coach_bot.stop()


def make_app() -> web.Application:
    app = web.Application(client_max_size=4 * 1024 * 1024)
    app.add_routes([
        web.post("/device/talk", talk),
        web.get("/device/inbox", inbox),
        web.get("/device/home", home),
        web.get("/device/screen/{rid}/{page:\\d+}", screen),
        web.get("/device/audio/{rid}", audio),
        web.get("/health", health),
    ])
    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), port=PORT)
