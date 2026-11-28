"""The virtual pet's state: it grows from your steps and workouts.

XP: 1 point per 100 steps, 25 per logged workout, 2 per chat.
Stages: egg -> baby -> kid -> teen -> adult.
Mood is a hint for the device's animation, from today's activity and time of day."""
import random
from datetime import datetime

import storage

STAGES = [("egg", 0), ("baby", 30), ("kid", 300), ("teen", 1200), ("adult", 3000)]
DEFAULT_NAME = "פיפו"

NUDGES = [
    "היי, ישבנו הרבה זמן... בוא נקום לסיבוב קצר? אני ממש רוצה לזוז!",
    "אני משתעמם! חמש דקות הליכה ואני מבטיח לשמוח כמו משוגע.",
    "רגע של מתיחות? הגב שלך יגיד תודה, ואני אקבל נקודות ניסיון.",
    "בוא נעשה סיבוב קטן ונשתה כוס מים בדרך. אתה ואני, צוות!",
    "הרגליים שלי נרדמות פה. קום רגע, נלך לכמה דקות?",
]


def name() -> str:
    return storage.get_profile().get("pet_name") or DEFAULT_NAME


def xp(now: datetime) -> int:
    steps_total = sum(storage.get_steps().values())
    workouts = len(storage.get_logs(3650, "workout", now))
    talks = storage.get_meta("talks", 0) or 0
    return steps_total // 100 + workouts * 25 + talks * 2


def state(now: datetime, steps_today: int, goal: int) -> dict:
    points = xp(now)
    stage, next_xp = STAGES[0][0], None
    for i, (s, need) in enumerate(STAGES):
        if points >= need:
            stage = s
            next_xp = STAGES[i + 1][1] if i + 1 < len(STAGES) else None
    hour = now.hour + now.minute / 60
    # by this hour, how many steps "should" we have (07:00-21:00 linear)?
    expected = goal * max(0.0, min(1.0, (hour - 7) / 14))
    if hour >= 23 or hour < 7:
        mood = "sleep"
    elif steps_today >= goal or (expected and steps_today >= expected):
        mood = "happy"
    elif hour >= 12 and steps_today < expected * 0.4:
        mood = "sad"
    else:
        mood = "ok"
    return {"name": name(), "stage": stage, "xp": points, "next_xp": next_xp,
            "mood": mood, "steps": steps_today, "goal": goal}


def nudge_text() -> str:
    return random.choice(NUDGES)
