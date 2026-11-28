"""Coach server — the brain behind the pocket pet (and the optional Telegram bot).

Device API (every request carries header X-Device-Key and ?steps=&batt=&w=&h=):
  GET  /device/state           -> {"pet": {...}, "msg": {"id","pages"} | null}
  POST /device/talk            body: raw PCM s16le 16kHz mono -> {"id","pages","text","pet"}
  GET  /device/screen/{id}/{n} -> w x h RGB565 speech-bubble page n of a reply
  GET  /device/audio/{id}      -> raw PCM s16le 16kHz mono speech of a reply
  GET  /device/stats           -> w x h RGB565 status card (name, stage, steps, XP)
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
import pet  # noqa: E402
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
SIT_MINUTES = int(os.environ.get("SIT_REMINDER_MINUTES", "90"))
NUDGE_FROM, NUDGE_UNTIL = 9, 21

# Replies rendered for the device, kept in memory for a while.
_replies: dict[str, dict] = {}
REPLY_TTL = 30 * 60


def _new_reply(text: str, size: tuple[int, int]) -> dict:
    now = time.time()
    for k in [k for k, v in _replies.items() if now - v["t"] > REPLY_TTL]:
        del _replies[k]
    rid = uuid.uuid4().hex[:10]
    r = {"t": now, "text": text, "pages": screens.reply_pages(text, *size), "audio": None}
    _replies[rid] = r
    return {"id": rid, "pages": len(r["pages"]), "text": text}


# ---------------------------------------------------------------- helpers
def _auth(req: web.Request) -> None:
    if not DEVICE_KEY or not hmac.compare_digest(req.headers.get("X-Device-Key", ""), DEVICE_KEY):
        raise web.HTTPUnauthorized()


def _size(req: web.Request) -> tuple[int, int]:
    try:
        w, h = int(req.query.get("w", 240)), int(req.query.get("h", 135))
    except ValueError:
        w, h = 240, 135
    return max(64, min(w, 480)), max(64, min(h, 480))


def _sync(req: web.Request) -> tuple[int, int | None]:
    """Every device request reports its pedometer and battery; record them."""
    day = brain.now().strftime("%Y-%m-%d")
    before = storage.get_steps().get(day, 0)
    try:
        today = storage.update_steps(int(req.query.get("steps", "")), day)
    except ValueError:
        today = before
    if today > before + 20:  # really moving, not a few stray counts
        storage.set_meta("last_move", brain.now().isoformat())
    try:
        batt = int(req.query.get("batt", ""))
    except ValueError:
        batt = None
    return today, batt


# ---------------------------------------------------------------- device API
def _pet(today: int) -> dict:
    return pet.state(brain.now(), today, STEP_GOAL)


async def state(req: web.Request) -> web.Response:
    _auth(req)
    today, _ = _sync(req)
    text = storage.pop_outbox()
    msg = None
    if text:
        r = _new_reply(text, _size(req))
        msg = {"id": r["id"], "pages": r["pages"]}
    return web.json_response({"pet": _pet(today), "msg": msg})


async def talk(req: web.Request) -> web.Response:
    _auth(req)
    today, _ = _sync(req)
    size = _size(req)
    pcm = await req.read()
    if len(pcm) < 16000:  # < 0.5s
        return web.json_response({"error": "too short"}, status=400)
    try:
        heard = await asyncio.to_thread(voice.transcribe, pcm)
    except Exception:
        logger.exception("speech-to-text failed")
        return web.json_response(_new_reply("לא הצלחתי לשמוע. נסה שוב?", size))
    logger.info("heard: %s", heard)
    if not heard:
        return web.json_response(_new_reply("לא שמעתי כלום, נסה לדבר קרוב יותר אליי.", size))
    storage.set_meta("talks", (storage.get_meta("talks", 0) or 0) + 1)
    try:
        answer = await asyncio.to_thread(brain.chat, heard, f"[בקול מהמכשיר] {heard}",
                                         lambda r: None, "device", _pet(today))
    except Exception:
        logger.exception("Claude call failed")
        answer = "יש לי תקלה רגעית בחיבור. נסה שוב עוד דקה."
    r = _new_reply(answer, size)
    r["pet"] = _pet(storage.get_steps().get(brain.now().strftime("%Y-%m-%d"), 0))
    return web.json_response(r)


async def stats(req: web.Request) -> web.Response:
    _auth(req)
    today, batt = _sync(req)
    img = screens.stats_card(_pet(today), today, STEP_GOAL, batt, *_size(req))
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
    """Send a proactive message to the pet (it chirps + speaks) and Telegram."""
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
                    today_steps = storage.get_steps().get(today, 0)
                    text = await asyncio.to_thread(brain.chat, p, p, lambda r: None, "device",
                                                   _pet(today_steps))
                    await _deliver(text)
            await _maybe_nudge(n)
        except Exception:
            logger.exception("scheduler tick failed")
        await asyncio.sleep(30)


async def _maybe_nudge(n: datetime) -> None:
    """Sitting still for too long during the day -> the pet asks you to move."""
    if not (NUDGE_FROM <= n.hour < NUDGE_UNTIL):
        return
    last_move = storage.get_meta("last_move")
    last_nudge = storage.get_meta("last_nudge")
    if not last_move:
        storage.set_meta("last_move", n.isoformat())
        return
    idle = (n - datetime.fromisoformat(last_move)).total_seconds() / 60
    since_nudge = (n - datetime.fromisoformat(last_nudge)).total_seconds() / 60 if last_nudge else 1e9
    if idle >= SIT_MINUTES and since_nudge >= SIT_MINUTES:
        storage.set_meta("last_nudge", n.isoformat())
        storage.push_outbox(pet.nudge_text())  # device only; no need to ping Telegram


def _minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


# ---------------------------------------------------------------- main
async def _on_startup(app: web.Application) -> None:
    if not DEVICE_KEY:
        logger.warning("DEVICE_KEY is not set — the device API will reject every request")
    if not voice.is_configured():
        logger.warning("ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not set — the pet can't hear or speak")
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
        web.get("/device/state", state),
        web.post("/device/talk", talk),
        web.get("/device/stats", stats),
        web.get("/device/screen/{rid}/{page:\\d+}", screen),
        web.get("/device/audio/{rid}", audio),
        web.get("/health", health),
    ])
    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), port=PORT)
