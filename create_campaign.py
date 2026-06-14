"""
יצירת קמפיין אוטומטית ב-Adcash דרך דפדפן (Playwright)
הסקריפט מתחבר, ממלא את הטופס ומגיש קמפיין חדש.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

EMAIL    = os.environ.get("ADCASH_EMAIL", "nadavi256@gmail.com")
PASSWORD = os.environ.get("ADCASH_PASSWORD", "abab10ab!!!")
LOGO_PATH = Path(__file__).parent / "logo.png"

# ── פרטי הקמפיין ──────────────────────────────────────────────────────────────
CAMPAIGN_NAME  = "קונים בזול - טלגרם"
GEO            = "IL"           # ישראל בלבד
DAILY_BUDGET   = "10"           # דולר ליום
BID            = "0.001"        # ביד מינימלי
LANDING_URL    = "https://t.me/alikibali"
AD_TITLE       = "קונים בזול באלי אקספרס 🛒"
AD_DESCRIPTION = "הצטרף לקבוצה – דילים בלעדיים בטלגרם!"
# ──────────────────────────────────────────────────────────────────────────────


async def login(page):
    """מתחבר ל-Adcash עם אימייל וסיסמה."""
    logger.info("מתחבר ל-Adcash...")
    await page.goto("https://adcash.myadcash.com/login", wait_until="networkidle")

    # לחץ על "Sign in with email" אם קיים, אחרת מלא ישירות
    try:
        email_btn = page.locator("text=Sign in with email, text=Login with email").first
        if await email_btn.is_visible(timeout=3000):
            await email_btn.click()
    except Exception:
        pass

    await page.fill('input[type="email"], input[name="email"], input[name="username"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await page.wait_for_url("**/dashboard/**", timeout=20000)
    logger.info("מחובר בהצלחה!")


async def step1_general(page):
    """שלב 1: שם קמפיין + geo."""
    logger.info("שלב 1 – פרטים כלליים")
    await page.goto("https://adcash.myadcash.com/dashboard/campaigns/create", wait_until="networkidle")

    # שם קמפיין
    await page.fill('input[placeholder*="Name"], input[name*="name"], input[id*="name"]', CAMPAIGN_NAME)

    # Geo targeting – Selected Locations
    try:
        await page.click("text=Selected Locations")
        await asyncio.sleep(1)
        geo_input = page.locator('input[placeholder*="country"], input[placeholder*="location"], input[placeholder*="search"]').first
        await geo_input.fill("Israel")
        await asyncio.sleep(1)
        await page.click("text=Israel")
    except Exception as e:
        logger.warning(f"Geo targeting: {e} – ממשיך עם Worldwide")

    await page.click("text=Next")
    await asyncio.sleep(2)
    logger.info("שלב 1 הושלם")


async def step2_targeting(page):
    """שלב 2: Targeting (ברירת מחדל – כל המכשירים)."""
    logger.info("שלב 2 – Targeting (ברירת מחדל)")
    await page.click("text=Next")
    await asyncio.sleep(2)


async def step3_creatives(page):
    """שלב 3: Creative – In-Page Push."""
    logger.info("שלב 3 – Creative: In-Page Push")

    # בחירת סוג creative
    await page.click("text=In-Page Push")
    await asyncio.sleep(1)

    # כותרת
    title_input = page.locator('input[name*="title"], input[placeholder*="title"], input[maxlength="30"]').first
    await title_input.fill(AD_TITLE[:30])

    # תיאור
    desc_input = page.locator('input[name*="description"], textarea[name*="description"], input[maxlength="45"]').first
    await desc_input.fill(AD_DESCRIPTION[:45])

    # URL יעד
    url_input = page.locator('input[name*="url"], input[placeholder*="http"], input[type="url"]').first
    await url_input.fill(LANDING_URL)

    # העלאת לוגו
    if LOGO_PATH.exists():
        try:
            file_input = page.locator('input[type="file"]').first
            await file_input.set_input_files(str(LOGO_PATH))
            await asyncio.sleep(2)
            logger.info("לוגו הועלה בהצלחה")
        except Exception as e:
            logger.warning(f"העלאת תמונה: {e}")
    else:
        logger.warning(f"קובץ לוגו לא נמצא: {LOGO_PATH}")

    # שמור ועבור הלאה
    try:
        await page.click("text=Save creative, text=Add creative, text=Save")
        await asyncio.sleep(1)
    except Exception:
        pass

    await page.click("text=Next")
    await asyncio.sleep(2)
    logger.info("שלב 3 הושלם")


async def step4_budget(page):
    """שלב 4: תקציב וביד."""
    logger.info("שלב 4 – תקציב")

    # תקציב יומי
    budget_input = page.locator('input[name*="budget"], input[placeholder*="budget"]').first
    await budget_input.fill(DAILY_BUDGET)

    # ביד
    bid_input = page.locator('input[name*="bid"], input[placeholder*="bid"], input[name*="cpc"]').first
    await bid_input.fill(BID)

    await page.click("text=Next")
    await asyncio.sleep(2)
    logger.info("שלב 4 הושלם")


async def step5_submit(page):
    """שלב 5: Overview + Submit."""
    logger.info("שלב 5 – שליחה")
    await asyncio.sleep(1)

    # לחץ Submit / Create Campaign / Launch
    submit_btn = page.locator(
        'button:has-text("Submit"), button:has-text("Create"), button:has-text("Launch"), button:has-text("Publish")'
    ).first
    await submit_btn.click()
    await asyncio.sleep(3)
    logger.info("✅ קמפיין נשלח!")


async def create_campaign():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="he-IL",
        )
        page = await ctx.new_page()

        # יירוט בקשות API לתיעוד
        api_calls = []
        page.on("request", lambda req: api_calls.append(req.url) if "api" in req.url else None)

        try:
            await login(page)
            await step1_general(page)
            await step2_targeting(page)
            await step3_creatives(page)
            await step4_budget(page)
            await step5_submit(page)

            # הדפס את קריאות ה-API שנלכדו
            logger.info("\n── קריאות API שנלכדו ──")
            for url in api_calls:
                logger.info(f"  {url}")

        except Exception as e:
            logger.error(f"שגיאה: {e}")
            await page.screenshot(path="error_screenshot.png")
            logger.info("צילום מסך נשמר: error_screenshot.png")
        finally:
            await browser.close()


if __name__ == "__main__":
    if not LOGO_PATH.exists():
        logger.warning(f"⚠️  לא נמצא קובץ logo.png ב-{LOGO_PATH}")
        logger.warning("שמור את הלוגו כ-logo.png בתיקיית הפרויקט והרץ שוב")
        sys.exit(1)
    asyncio.run(create_campaign())
