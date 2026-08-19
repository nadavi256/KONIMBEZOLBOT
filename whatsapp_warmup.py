"""Volume ramp-up for a freshly-connected WhatsApp number.

A brand new number that jumps straight to a high send volume is the
clearest way to get flagged. This module spreads a target daily volume
evenly across the active window, and raises that target gradually over
RAMP_DAYS starting from the day automated sending first actually ran
(see whatsapp_tracker.get_or_start_warmup) — not from whenever this code
happens to be deployed.
"""
import os

ACTIVE_WINDOW_MINUTES = 13 * 60  # 09:00–22:00

WARMUP_START_CAP = int(os.environ.get("WHATSAPP_WARMUP_START_CAP", "6"))
TARGET_DAILY_CAP = int(os.environ.get("WHATSAPP_TARGET_DAILY_CAP", "52"))
RAMP_DAYS = int(os.environ.get("WHATSAPP_RAMP_DAYS", "14"))


def compute_daily_cap(days_since_start: int) -> int:
    """Today's allowed send count, linearly ramping from WARMUP_START_CAP
    (day 0, a brand new number) up to TARGET_DAILY_CAP over RAMP_DAYS."""
    days_since_start = max(0, days_since_start)
    if days_since_start >= RAMP_DAYS:
        return TARGET_DAILY_CAP
    progress = days_since_start / RAMP_DAYS
    return round(WARMUP_START_CAP + (TARGET_DAILY_CAP - WARMUP_START_CAP) * progress)


def compute_min_gap_minutes(daily_cap: int) -> float:
    """Minimum minutes between sends so `daily_cap` sends spread evenly
    across the active window, instead of clustering early in the day."""
    if daily_cap <= 0:
        return float("inf")
    return ACTIVE_WINDOW_MINUTES / daily_cap
