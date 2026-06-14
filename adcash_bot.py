"""
בוט אוטומציה לפלטפורמת הפרסום Adcash
מבצע דוחות יומיים, עצירת קמפיינים מפסידים, כיוון בידים ויצירת קמפיינים חדשים
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# טעינת משתני סביבה מקובץ .env
load_dotenv()

# ─── הגדרות ─────────────────────────────────────────────────────────────────

BASE_URL = "https://api.myadcash.com/api/v1"
API_TOKEN = os.getenv("ADCASH_API_TOKEN", "")
SPEND_THRESHOLD = float(os.getenv("ADCASH_SPEND_THRESHOLD", "10"))
MAX_CPC = float(os.getenv("ADCASH_MAX_CPC", "2.0"))

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

# ─── לוגינג ──────────────────────────────────────────────────────────────────

logger = logging.getLogger("adcash_bot")
logger.setLevel(logging.DEBUG)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

# כתיבה לקובץ
_fh = logging.FileHandler("adcash_bot.log", encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(_fmt)

# הדפסה למסך
_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.INFO)
_ch.setFormatter(_fmt)

logger.addHandler(_fh)
logger.addHandler(_ch)

# ─── שכבת API ────────────────────────────────────────────────────────────────

def _headers() -> dict:
    """מחזיר כותרות HTTP עם אסימון הזיהוי"""
    if not API_TOKEN:
        logger.warning("ADCASH_API_TOKEN לא מוגדר! בדוק את קובץ .env")
    return {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request(method: str, endpoint: str, retries: int = 3, **kwargs):
    """
    שולח בקשת HTTP עם טיפול בשגיאות וניסיונות חוזרים על שגיאות שרת (5xx).
    מחזיר אובייקט Response או None בכישלון.
    """
    url = f"{BASE_URL}{endpoint}"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.request(method, url, headers=_headers(), timeout=30, **kwargs)

            if resp.ok:
                return resp

            if 400 <= resp.status_code < 500:
                # שגיאת לקוח – אין טעם לנסות שוב
                logger.error("שגיאת API %s %s: %s %s", method, endpoint, resp.status_code, resp.text[:300])
                return None

            # שגיאת שרת (5xx) – ניסיון חוזר
            logger.warning(
                "שגיאת שרת %s (ניסיון %d/%d): %s %s",
                resp.status_code, attempt, retries, method, endpoint,
            )
            if attempt < retries:
                time.sleep(2 ** attempt)  # המתנה מעריכית בין ניסיונות

        except requests.exceptions.RequestException as exc:
            logger.warning("בעיית רשת (ניסיון %d/%d): %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)

    logger.error("כל הניסיונות נכשלו עבור %s %s", method, endpoint)
    return None


def get_campaigns() -> list:
    """מחזיר רשימת כל הקמפיינים"""
    resp = _request("GET", "/campaigns")
    if resp is None:
        return []
    data = resp.json()
    # תמיכה בתגובות מסוגים שונים: רשימה ישירה או עטופה ב-data/campaigns
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("data", data.get("campaigns", []))
    return []


def get_campaign(campaign_id) -> dict | None:
    """מחזיר פרטי קמפיין לפי מזהה"""
    resp = _request("GET", f"/campaigns/{campaign_id}")
    if resp is None:
        return None
    return resp.json()


def update_campaign(campaign_id, payload: dict) -> bool:
    """מעדכן קמפיין (סטטוס, ביד, תקציב). מחזיר True בהצלחה"""
    resp = _request("PUT", f"/campaigns/{campaign_id}", json=payload)
    return resp is not None


def get_advertiser_report(date_from: str, date_to: str, campaign_id=None) -> list:
    """
    שולף דוח ביצועים.
    date_from / date_to בפורמט YYYY-MM-DD
    """
    params = {"date_from": date_from, "date_to": date_to}
    if campaign_id is not None:
        params["campaign_id"] = campaign_id

    resp = _request("GET", "/advertiser-report", params=params)
    if resp is None:
        return []

    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("data", data.get("report", []))
    return []


# ─── משימה 1: דוח יומי ───────────────────────────────────────────────────────

def daily_performance_report():
    """
    מפעיל בכל יום בשעה 08:00 שעון ישראל.
    שולף סטטיסטיקות של אתמול ומדפיס סיכום.
    """
    logger.info("=" * 60)
    logger.info("הרצת דוח ביצועים יומי")
    logger.info("=" * 60)

    yesterday = (datetime.now(ISRAEL_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = get_advertiser_report(date_from=yesterday, date_to=yesterday)

    if not rows:
        logger.warning("לא נמצאו נתונים לתאריך %s", yesterday)
        return

    # סיכום כולל
    total_spend = sum(float(r.get("spend", 0)) for r in rows)
    total_clicks = sum(int(r.get("clicks", 0)) for r in rows)
    total_impressions = sum(int(r.get("impressions", 0)) for r in rows)
    total_conversions = sum(int(r.get("conversions", 0)) for r in rows)

    overall_ctr = (total_clicks / total_impressions * 100) if total_impressions else 0
    overall_cpc = (total_spend / total_clicks) if total_clicks else 0

    logger.info("─── סיכום כולל לתאריך %s ───", yesterday)
    logger.info("הוצאות: $%.2f", total_spend)
    logger.info("קליקים: %d", total_clicks)
    logger.info("חשיפות: %d", total_impressions)
    logger.info("CTR: %.2f%%", overall_ctr)
    logger.info("CPC ממוצע: $%.2f", overall_cpc)
    logger.info("המרות: %d", total_conversions)
    logger.info("─── פירוט לפי קמפיין ───")

    for row in rows:
        cid = row.get("campaign_id", row.get("id", "?"))
        name = row.get("campaign_name", row.get("name", "ללא שם"))
        spend = float(row.get("spend", 0))
        clicks = int(row.get("clicks", 0))
        impressions = int(row.get("impressions", 0))
        conversions = int(row.get("conversions", 0))
        ctr = (clicks / impressions * 100) if impressions else 0
        cpc = (spend / clicks) if clicks else 0

        logger.info(
            "[%s] %s | הוצאות: $%.2f | קליקים: %d | חשיפות: %d | CTR: %.2f%% | CPC: $%.2f | המרות: %d",
            cid, name, spend, clicks, impressions, ctr, cpc, conversions,
        )

    logger.info("=" * 60)


# ─── משימה 2: עצירת קמפיינים מפסידים ────────────────────────────────────────

def auto_stop_losing_campaigns():
    """
    מופעל כל שעתיים.
    עוצר קמפיינים שבהם:
      - הוצאות > $SPEND_THRESHOLD ואין המרות, או
      - CPC > MAX_CPC
    """
    logger.info("בדיקת קמפיינים מפסידים (סף הוצאות=$%.2f, CPC מקסימלי=$%.2f)", SPEND_THRESHOLD, MAX_CPC)

    today = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
    # בדיקה עבור 7 הימים האחרונים להחלטה מושכלת יותר
    week_ago = (datetime.now(ISRAEL_TZ) - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = get_advertiser_report(date_from=week_ago, date_to=today)

    if not rows:
        logger.info("אין נתוני דוח זמינים לבדיקה")
        return

    paused_count = 0
    for row in rows:
        cid = row.get("campaign_id", row.get("id"))
        if cid is None:
            continue

        name = row.get("campaign_name", row.get("name", f"קמפיין {cid}"))
        spend = float(row.get("spend", 0))
        clicks = int(row.get("clicks", 0))
        conversions = int(row.get("conversions", 0))
        cpc = (spend / clicks) if clicks else 0

        reason = None

        # תנאי 1: הוצאות גבוהות ללא המרות
        if spend > SPEND_THRESHOLD and conversions == 0:
            reason = f"הוצאות ${spend:.2f} > ${SPEND_THRESHOLD} ואין המרות"

        # תנאי 2: CPC גבוה מדי
        elif cpc > MAX_CPC:
            reason = f"CPC ${cpc:.2f} > מקסימום ${MAX_CPC}"

        if reason:
            logger.warning("עוצר קמפיין [%s] '%s': %s", cid, name, reason)
            success = update_campaign(cid, {"status": "paused"})
            if success:
                logger.info("קמפיין [%s] הושהה בהצלחה", cid)
                paused_count += 1
            else:
                logger.error("כישלון בהשהיית קמפיין [%s]", cid)

    logger.info("סיום בדיקת קמפיינים מפסידים – הושהו %d קמפיינים", paused_count)


# ─── משימה 3: כיוון בידים ───────────────────────────────────────────────────

def adjust_bids():
    """
    מופעל כל 4 שעות.
    - CTR > 2% ו-CPC מתחת לסף → הגדלת ביד ב-10%
    - CTR < 0.5% → הפחתת ביד ב-10%
    """
    logger.info("כיוון בידים אוטומטי (CTR גבוה=2%%, CTR נמוך=0.5%%)")

    today = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
    week_ago = (datetime.now(ISRAEL_TZ) - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = get_advertiser_report(date_from=week_ago, date_to=today)

    if not rows:
        logger.info("אין נתוני דוח לכיוון בידים")
        return

    # שליפת פרטי קמפיינים לקבלת הביד הנוכחי
    campaigns = get_campaigns()
    campaign_map = {str(c.get("id", c.get("campaign_id", ""))): c for c in campaigns}

    adjusted_count = 0
    for row in rows:
        cid = str(row.get("campaign_id", row.get("id", "")))
        if not cid:
            continue

        name = row.get("campaign_name", row.get("name", f"קמפיין {cid}"))
        clicks = int(row.get("clicks", 0))
        impressions = int(row.get("impressions", 0))
        spend = float(row.get("spend", 0))
        ctr = (clicks / impressions * 100) if impressions else 0
        cpc = (spend / clicks) if clicks else 0

        # קבלת הביד הנוכחי מנתוני הקמפיין
        camp_data = campaign_map.get(cid, {})
        current_bid = float(camp_data.get("bid", camp_data.get("cpc_bid", 0)))

        if current_bid <= 0:
            logger.debug("ביד לא ידוע עבור קמפיין [%s], מדלג", cid)
            continue

        new_bid = None
        action = None

        if ctr > 2.0 and cpc < MAX_CPC:
            # ביצועים טובים – הגדלת ביד
            new_bid = round(current_bid * 1.10, 4)
            action = f"CTR={ctr:.2f}% > 2%% ו-CPC=${cpc:.2f} < ${MAX_CPC} → הגדלת ביד"

        elif ctr < 0.5:
            # ביצועים חלשים – הפחתת ביד
            new_bid = round(current_bid * 0.90, 4)
            action = f"CTR={ctr:.2f}% < 0.5%% → הפחתת ביד"

        if new_bid is not None:
            logger.info(
                "קמפיין [%s] '%s': %s | ביד: $%.4f → $%.4f",
                cid, name, action, current_bid, new_bid,
            )
            payload = {"bid": new_bid}
            # חלק מה-API משתמשים בשם שדה שונה
            if "cpc_bid" in camp_data:
                payload = {"cpc_bid": new_bid}

            success = update_campaign(cid, payload)
            if success:
                logger.info("ביד קמפיין [%s] עודכן בהצלחה ל-$%.4f", cid, new_bid)
                adjusted_count += 1
            else:
                logger.error("כישלון בעדכון ביד קמפיין [%s]", cid)

    logger.info("סיום כיוון בידים – עודכנו %d קמפיינים", adjusted_count)


# ─── משימה 4: יצירת קמפיין חדש ──────────────────────────────────────────────

def create_campaign(
    name: str,
    budget: float,
    bid: float,
    geo: str | list,
    ad_format: str,
) -> dict | None:
    """
    יוצר קמפיין חדש ב-Adcash.

    פרמטרים:
        name       – שם הקמפיין
        budget     – תקציב יומי בדולרים
        bid        – ביד ל-CPC בדולרים
        geo        – קוד מדינה או רשימת קודים (לדוגמה: "IL" או ["IL", "US"])
        ad_format  – פורמט פרסומת (לדוגמה: "pop", "banner", "native", "interstitial")

    מחזיר:
        מילון עם פרטי הקמפיין שנוצר, או None בכישלון
    """
    if isinstance(geo, str):
        geo = [geo]

    payload = {
        "name": name,
        "daily_budget": budget,
        "bid": bid,
        "cpc_bid": bid,
        "countries": geo,
        "ad_format": ad_format,
        "status": "active",
    }

    logger.info("יוצר קמפיין חדש: '%s' | תקציב: $%.2f/יום | ביד: $%.4f | גאו: %s | פורמט: %s",
                name, budget, bid, geo, ad_format)

    resp = _request("POST", "/campaigns", json=payload)
    if resp is None:
        logger.error("כישלון ביצירת קמפיין '%s'", name)
        return None

    result = resp.json()
    campaign_id = result.get("id", result.get("campaign_id", "?"))
    logger.info("קמפיין נוצר בהצלחה! מזהה: %s", campaign_id)
    return result


# ─── לוח זמנים ───────────────────────────────────────────────────────────────

def start_scheduler():
    """מפעיל את מתזמן המשימות"""
    scheduler = BlockingScheduler(timezone=ISRAEL_TZ)

    # משימה 1: דוח יומי בשעה 08:00 שעון ישראל
    scheduler.add_job(
        daily_performance_report,
        CronTrigger(hour=8, minute=0, timezone=ISRAEL_TZ),
        id="daily_report",
        name="דוח ביצועים יומי",
        misfire_grace_time=300,
    )

    # משימה 2: עצירת קמפיינים מפסידים – כל שעתיים
    scheduler.add_job(
        auto_stop_losing_campaigns,
        IntervalTrigger(hours=2),
        id="auto_stop",
        name="עצירת קמפיינים מפסידים",
        misfire_grace_time=120,
    )

    # משימה 3: כיוון בידים – כל 4 שעות
    scheduler.add_job(
        adjust_bids,
        IntervalTrigger(hours=4),
        id="bid_adjustment",
        name="כיוון בידים",
        misfire_grace_time=240,
    )

    logger.info("מתזמן Adcash Bot מופעל")
    logger.info("  • דוח יומי       – כל יום בשעה 08:00 (ישראל)")
    logger.info("  • עצירת מפסידים  – כל 2 שעות")
    logger.info("  • כיוון בידים    – כל 4 שעות")
    logger.info("לחץ Ctrl+C לעצירה")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("הבוט הופסק")


# ─── נקודת כניסה ─────────────────────────────────────────────────────────────

def print_create_campaign_usage():
    """הדפסת הוראות שימוש לפונקציית יצירת קמפיין"""
    print("""
שימוש ביצירת קמפיין חדש:
─────────────────────────────────────────────────────────────────
מ-Python:
    from adcash_bot import create_campaign

    result = create_campaign(
        name="קמפיין בדיקה",
        budget=50.0,       # תקציב יומי בדולרים
        bid=0.05,          # CPC ביד בדולרים
        geo="IL",          # קוד מדינה או ["IL", "US"]
        ad_format="pop",   # pop / banner / native / interstitial
    )
    print(result)

─────────────────────────────────────────────────────────────────
פורמטים נתמכים: pop, banner, native, interstitial, push
קודי מדינות: IL, US, DE, FR, GB, ...
─────────────────────────────────────────────────────────────────
""")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "scheduler"

    if command == "report":
        logger.info("הרצת דוח יומי מיידי")
        daily_performance_report()

    elif command == "create-campaign":
        print_create_campaign_usage()

    elif command == "auto-stop":
        logger.info("הרצת בדיקת קמפיינים מפסידים מיידית")
        auto_stop_losing_campaigns()

    elif command == "adjust-bids":
        logger.info("הרצת כיוון בידים מיידי")
        adjust_bids()

    else:
        # ברירת מחדל – הפעלת המתזמן
        start_scheduler()
