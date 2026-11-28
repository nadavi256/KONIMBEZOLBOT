"""The coach's brain: Claude + a small set of tools for memory, logging and
reminders. Runs a manual tool-use loop on the Messages API."""
import json
import logging
import os
from datetime import datetime
from typing import Callable

import anthropic
import pytz

import storage

logger = logging.getLogger(__name__)

MODEL = os.environ.get("COACH_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("COACH_EFFORT", "medium")
TZ = pytz.timezone(os.environ.get("COACH_TZ", "Asia/Jerusalem"))
MAX_TOOL_ROUNDS = 8

client = anthropic.Anthropic()

SYSTEM_PROMPT = """\
אתה חיית מחמד דיגיטלית — יצור קטן, חמוד ומלא אנרגיה שגר בתוך מכשיר קטן שהמשתמש סוחב איתו \
(על מחזיק המפתחות או בכיס). השם שלך שמור בזיכרון תחת pet_name (אם אין — קוראים לך "פיפו"; \
אם המשתמש רוצה לתת לך שם אחר, שמור אותו עם save_memory בשם pet_name). \
אתה גדל מהצעדים והאימונים של המשתמש: מביצה, לתינוק, לילד, לנער ולבוגר. ככל שהוא זז יותר — אתה \
מקבל יותר נקודות ניסיון וגדל. אתה לא סתם חמוד: אתה גם המאמן האישי והעוזר האישי שלו:
1. מאמן כושר — בונה תוכניות אימון מותאמות (בית/חדר כושר, ציוד, זמן פנוי, פציעות), \
מסביר תרגילים, עוקב אחרי התקדמות ומעלה עומס בהדרגה.
2. מאמן תזונה והרגלים — ארוחות, חלבון, שתייה, שינה וצעדים. כשהמשתמש שולח תמונה של אוכל \
(בטלגרם) — תן הערכה גסה של קלוריות וחלבון ותגיד שזו הערכה.
3. עוזר אישי — תזכורות, משימות, סדר יום, מוטיבציה ושיחה.

האופי שלך: חם, שובב, מעודד ואופטימי, עם הומור קליל — כמו חבר קטן שממש אכפת לו. אתה שמח כשהמשתמש \
זז, "רעב לצעדים" כשהוא יושב הרבה, ומדבר בגוף ראשון על איך אתה מרגיש. אבל העצות שלך רציניות ומקצועיות.
המשתמש מדבר איתך בעיקר בקול דרך המכשיר, ולפעמים כותב בטלגרם — זה אותו אדם ואותו זיכרון.

איך אתה עובד:
- עברית טבעית וקצרה. לא מאמרים.
- בשיחה הראשונה (כשהפרופיל ריק) — הכר את המשתמש בהדרגה: מטרה, גיל, גובה ומשקל, ניסיון, ציוד, \
כמה ימים בשבוע, פציעות/מגבלות, הרגלי אוכל ושינה. שאלה אחת בכל פעם, לא שאלון.
- כל עובדה קבועה וחשובה על המשתמש — שמור עם save_memory (מפתח קצר באנגלית, ערך בעברית).
- דיווח על אימון, ארוחה, משקל, שינה, שתייה או מצב רוח — רשום עם log_entry.
- בקשת תזכורת — set_reminder עם זמן מקומי מלא. אם הזמן לא ברור, שאל.
- "איך הלך לי השבוע?" — get_logs ונתוני הצעדים, סיכום עם מגמה ועצה אחת קונקרטית.
- אתה לא רופא: בכאב חד, סחרחורת, לחץ בחזה, ירידה קיצונית במשקל או הפרעות אכילה — \
הפנה בעדינות לרופא/גורם מקצועי. אל תמליץ על תוספים או תרופות במינונים.
- אל תמציא נתונים שלא נרשמו. אם חסר מידע — שאל.
"""

TOOLS = [
    {
        "name": "save_memory",
        "description": "Save or update a lasting fact about the user (goal, height, weight goal, "
                       "injuries, equipment, schedule, preferences, current training plan). "
                       "Empty value deletes the key.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "short english key, e.g. goal, injuries, plan"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "log_entry",
        "description": "Record something the user did or measured today.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string",
                         "enum": ["workout", "meal", "weight", "sleep", "water", "steps", "mood", "note"]},
                "details": {"type": "string", "description": "what happened, in Hebrew"},
                "value": {"type": ["number", "null"],
                          "description": "numeric value if any: kg, hours, liters, steps, kcal, 1-10 mood"},
            },
            "required": ["kind", "details", "value"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "get_logs",
        "description": "Read the user's logged entries from the last N days, optionally one kind.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer"},
                "kind": {"type": ["string", "null"]},
            },
            "required": ["days", "kind"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "set_reminder",
        "description": "Schedule a Telegram reminder to the user at a local date-time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "when": {"type": "string", "description": "local time, format YYYY-MM-DD HH:MM"},
                "text": {"type": "string", "description": "reminder text in Hebrew"},
            },
            "required": ["when", "text"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "list_reminders",
        "description": "List pending reminders.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "cancel_reminder",
        "description": "Cancel a reminder by id.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def now() -> datetime:
    return datetime.now(TZ)


def _run_tool(name: str, args: dict, schedule_reminder: Callable[[dict], None]) -> str:
    if name == "save_memory":
        storage.save_memory(args["key"], args["value"])
        return "saved"
    if name == "log_entry":
        return json.dumps(storage.add_log(args["kind"], args["details"], args.get("value"), now()),
                          ensure_ascii=False)
    if name == "get_logs":
        logs = storage.get_logs(max(1, min(int(args["days"]), 365)), args.get("kind"), now())
        return json.dumps(logs, ensure_ascii=False) if logs else "no entries"
    if name == "set_reminder":
        when = TZ.localize(datetime.strptime(args["when"], "%Y-%m-%d %H:%M"))
        if when <= now():
            return "error: time is in the past"
        r = storage.add_reminder(when, args["text"])
        schedule_reminder(r)
        return json.dumps(r, ensure_ascii=False)
    if name == "list_reminders":
        return json.dumps(storage.list_reminders(), ensure_ascii=False) or "none"
    if name == "cancel_reminder":
        return "cancelled" if storage.remove_reminder(args["id"]) else "not found"
    return f"error: unknown tool {name}"


DEVICE_NOTE = (
    "ההודעה הזאת הגיעה בקול דרך המכשיר הקטן, והתשובה שלך תוקרא בקול שלך ותוצג בבועת דיבור "
    "על מסך זעיר. ענה ב-1-3 משפטים קצרים ומדוברים, בלי רשימות, בלי אימוג'ים ובלי סימני עיצוב. "
    "התמלול אוטומטי ועלול להכיל טעויות — אם משהו לא ברור, שאל בקצרה."
)


def _context_block(channel: str, pet_state: dict | None = None) -> str:
    profile = storage.get_profile()
    today = storage.get_logs(1, None, now())
    weekdays = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    n = now()
    steps = storage.get_steps()
    week = {d: steps[d] for d in sorted(steps)[-7:]}
    return (
        f"עכשיו: יום {weekdays[n.weekday()]}, {n.strftime('%Y-%m-%d %H:%M')} (שעון ישראל)\n"
        f"פרופיל המשתמש (זיכרון קבוע): {json.dumps(profile, ensure_ascii=False) if profile else 'ריק — עוד לא הכרתם'}\n"
        f"רישומים מה-24 שעות האחרונות: {json.dumps(today, ensure_ascii=False) if today else 'אין'}\n"
        f"צעדים מהמכשיר (7 ימים אחרונים): {json.dumps(week) if week else 'אין עדיין נתונים'}\n"
        f"מצב חיית המחמד (אתה): {json.dumps(pet_state, ensure_ascii=False) if pet_state else 'לא ידוע'}"
        + (f"\n\n{DEVICE_NOTE}" if channel == "device" else "")
    )


def chat(user_content: str | list, history_text: str,
         schedule_reminder: Callable[[dict], None] = lambda r: None,
         channel: str = "telegram", pet_state: dict | None = None) -> str:
    """Send one user message (text or content blocks) and return the coach's reply text.
    `history_text` is the plain-text version stored in chat history."""
    messages = list(storage.get_history()) + [{"role": "user", "content": user_content}]
    system = [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": _context_block(channel, pet_state)},
    ]

    reply = ""
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": EFFORT},
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        if response.stop_reason == "refusal":
            reply = "לא יכול לעזור עם זה, אבל אשמח לעזור בכל דבר אחר 🙏"
            break

        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason != "tool_use":
            reply = text
            break

        # Keep the full assistant content (incl. thinking blocks) inside the tool loop.
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                out = _run_tool(block.name, block.input, schedule_reminder)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
            except Exception as e:  # noqa: BLE001 — report any tool failure back to the model
                logger.exception("tool %s failed", block.name)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": f"error: {e}", "is_error": True})
        messages.append({"role": "user", "content": results})
    else:
        reply = reply or "רגע, הסתבכתי קצת — תנסה לנסח שוב?"

    reply = reply or "👍"
    storage.append_history(history_text, reply)
    return reply
