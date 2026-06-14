"""
יצירת קמפיין אוטומטית ב-Adcash – In-Page Push לקבוצת טלגרם
"""
import asyncio
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

EMAIL     = os.environ.get("ADCASH_EMAIL", "nadavi256@gmail.com")
PASSWORD  = os.environ.get("ADCASH_PASSWORD", "abab10ab!!!")
LOGO_PATH = Path(__file__).parent / "logo.png"

CAMPAIGN_NAME  = "קונים בזול - טלגרם"
LANDING_URL    = "https://t.me/alikibali"
AD_TITLE       = "קונים בזול באלי אקספרס"
AD_DESCRIPTION = "הצטרפו – דילים בלעדיים!"
DAILY_BUDGET   = "10"
BID            = "0.001"


async def next_step(page):
    """לוחץ Next דרך JS (עוקף chat widget שחוסם)."""
    await page.evaluate('''() => {
        // הסר chat widget
        const chat = document.getElementById("hubspot-messages-iframe-container");
        if (chat) chat.remove();
        // לחץ על כפתור Next
        const btn = document.getElementById("next-btn") ||
                    document.querySelector('button.btn-primary');
        if (btn) btn.click();
    }''')
    await asyncio.sleep(5)
    logger.info(f"  → {page.url}")


async def create_campaign():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        try:
            # ── Login ─────────────────────────────────────────────────────────
            logger.info("מתחבר...")
            await page.goto("https://adcash.myadcash.com/login", wait_until="domcontentloaded", timeout=30000)
            await page.fill('input[name="username"]', EMAIL)
            await page.fill('input[name="password"]', PASSWORD)
            await page.click('button[type="submit"]')
            await page.wait_for_url("**/dashboard/**", timeout=20000)
            logger.info("מחובר ✓")

            # ── שלב 1: General ────────────────────────────────────────────────
            logger.info("שלב 1 – שם קמפיין")
            await page.goto("https://adcash.myadcash.com/campaign/create", wait_until="networkidle", timeout=30000)
            await page.wait_for_selector('#generalupdateform-name', timeout=15000)
            await page.fill('#generalupdateform-name', CAMPAIGN_NAME)

            # גאו ישראל
            try:
                await page.click("label:has-text('Selected Locations')", timeout=5000)
                await asyncio.sleep(1)
                ms = page.locator('.multiselect__input').first
                await ms.click(timeout=5000)
                await ms.type("Israel", delay=80)
                await asyncio.sleep(1)
                await page.locator('.multiselect__element:has-text("Israel")').first.click(timeout=5000)
                logger.info("  גאו: Israel ✓")
            except Exception as e:
                logger.warning(f"  גאו: {e}")
                # חזור ל-Worldwide כדי לאפס את ה-multiselect
                try:
                    await page.click("label:has-text('Worldwide')", timeout=3000)
                    await asyncio.sleep(1)
                except Exception:
                    pass

            await next_step(page)
            logger.info("שלב 1 הושלם ✓")

            # ── שלב 2: Targeting ──────────────────────────────────────────────
            logger.info("שלב 2 – Targeting (ברירת מחדל)")
            await next_step(page)
            logger.info("שלב 2 הושלם ✓")

            # ── שלב 3: Creatives ──────────────────────────────────────────────
            logger.info("שלב 3 – Creative: In-Page Push")
            await asyncio.sleep(2)

            # בחר In-Page Push
            await page.evaluate('''() => {
                const match = Array.from(document.querySelectorAll("*"))
                    .find(e => e.innerText && e.innerText.trim() === "In-Page Push" && e.offsetParent !== null);
                if (match) match.click();
            }''')
            await asyncio.sleep(1)

            # כותרת
            await page.fill('#creative-title', AD_TITLE[:30])

            # URL (textarea ראשון עם placeholder https)
            await page.locator('textarea[placeholder*="http"]').first.fill(LANDING_URL)

            # תיאור (textarea שניה)
            desc_areas = page.locator('textarea[id="macros-input"]')
            n = await desc_areas.count()
            target_desc = desc_areas.nth(1) if n >= 2 else desc_areas.first
            await target_desc.fill(AD_DESCRIPTION[:45])

            # העלאת לוגו
            if LOGO_PATH.exists():
                await page.locator('input[name="ipp-file-upload"]').set_input_files(str(LOGO_PATH))
                await asyncio.sleep(3)
                logger.info("  לוגו הועלה ✓")
            else:
                logger.warning(f"  לוגו לא נמצא: {LOGO_PATH}")

            # שמור creative אם יש כפתור
            try:
                save = page.locator('button:has-text("Save creative"), button:has-text("Add creative")')
                if await save.count() > 0:
                    await save.first.click(timeout=5000)
                    await asyncio.sleep(1)
            except Exception:
                pass

            await next_step(page)
            logger.info("שלב 3 הושלם ✓")

            # ── שלב 4: Budget ─────────────────────────────────────────────────
            logger.info("שלב 4 – תקציב")
            await asyncio.sleep(2)

            # תקציב יומי (Cappings)
            try:
                await page.fill('#cappingform-turnover', DAILY_BUDGET)
                logger.info(f"  תקציב יומי: ${DAILY_BUDGET} ✓")
            except Exception as e:
                logger.warning(f"  תקציב: {e}")

            await next_step(page)
            logger.info("שלב 4 הושלם ✓")

            # ── שלב 5: Overview + Submit ──────────────────────────────────────
            logger.info("שלב 5 – Overview ושליחה")
            await asyncio.sleep(2)
            await page.screenshot(path="overview.png")

            # הכפתור הוא "Create a campaign" בדף Overview
            await page.evaluate('''() => {
                const chat = document.getElementById("hubspot-messages-iframe-container");
                if (chat) chat.remove();
                const btn = Array.from(document.querySelectorAll("a"))
                    .find(e => e.innerText.trim() === "Create a campaign" && e.offsetParent !== null);
                if (btn) btn.click();
            }''')
            await asyncio.sleep(5)
            await page.screenshot(path="campaign_created.png")
            logger.info(f"✅ קמפיין נוצר! URL: {page.url}")

        except Exception as e:
            logger.error(f"שגיאה: {e}")
            await page.screenshot(path="error.png")
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(create_campaign())
