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

            # גאו ישראל – לחץ על label של "Selected Locations", הקלד Israel, לחץ לפי קואורדינטות
            try:
                await page.evaluate('''() => {
                    const radio = document.querySelector('input[type="radio"][value="countries"]');
                    const label = document.querySelector(`label[for="${radio.id}"]`);
                    if (label) label.click();
                }''')
                await asyncio.sleep(1.5)

                # פוקוס ב-multiselect והקלד
                await page.evaluate('() => { const i = Array.from(document.querySelectorAll(".multiselect__input")).find(x=>x.offsetParent); if(i) i.focus(); }')
                await page.keyboard.type("Israel", delay=80)
                await asyncio.sleep(2)

                # לחץ על ה-option לפי קואורדינטות (Vue מגיב לזה)
                coords = await page.evaluate('''() => {
                    const els = Array.from(document.querySelectorAll(".multiselect__element"))
                        .filter(e => e.offsetParent !== null && (e.innerText||"").includes("Israel"));
                    if (els.length > 0) {
                        const r = els[0].getBoundingClientRect();
                        return {x: r.left + r.width/2, y: r.top + r.height/2};
                    }
                    return null;
                }''')
                if coords:
                    await page.mouse.click(coords['x'], coords['y'])
                    await asyncio.sleep(1)
                logger.info("  גאו: Israel ✓")
            except Exception as e:
                logger.warning(f"  גאו נכשל, נשאר Worldwide: {e}")

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
            await asyncio.sleep(2)

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

            # שמור creative (חובה לפני Next!)
            await page.evaluate('''() => {
                const btn = Array.from(document.querySelectorAll("button"))
                    .find(e => e.offsetParent !== null && e.innerText.includes("Save creative"));
                if (btn) btn.click();
            }''')
            await asyncio.sleep(3)
            logger.info("  Creative נשמר ✓")

            await next_step(page)
            logger.info("שלב 3 הושלם ✓")

            # ── שלב 4: Budget ─────────────────────────────────────────────────
            logger.info("שלב 4 – תקציב")
            await asyncio.sleep(3)

            # בחר CPC כסוג תשלום
            try:
                await page.evaluate('''() => {
                    const chat = document.getElementById("hubspot-messages-iframe-container");
                    if (chat) chat.remove();
                    const btn = Array.from(document.querySelectorAll("button, a, label, div"))
                        .find(e => e.offsetParent !== null && e.innerText && e.innerText.trim() === "CPC");
                    if (btn) btn.click();
                }''')
                await asyncio.sleep(2)
                logger.info("  CPC נבחר ✓")
            except Exception as e:
                logger.warning(f"  CPC: {e}")

            # שמור Bids (Save changes הראשון)
            try:
                await page.evaluate('''() => {
                    const chat = document.getElementById("hubspot-messages-iframe-container");
                    if (chat) chat.remove();
                    // מצא את כפתור "Save changes" הראשון הגלוי בדף
                    const btns = Array.from(document.querySelectorAll("button"))
                        .filter(e => e.offsetParent !== null && e.innerText.includes("Save changes"));
                    if (btns.length > 0) btns[0].click();
                }''')
                await asyncio.sleep(3)
                logger.info("  Bids נשמרו ✓")
            except Exception as e:
                logger.warning(f"  Save bids: {e}")

            # תקציב יומי (Cappings)
            try:
                await page.fill('#cappingform-turnover', DAILY_BUDGET)
                logger.info(f"  תקציב יומי: ${DAILY_BUDGET} ✓")
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"  תקציב: {e}")

            # שמור Cappings (Save changes השני)
            try:
                await page.evaluate('''() => {
                    const chat = document.getElementById("hubspot-messages-iframe-container");
                    if (chat) chat.remove();
                    const btns = Array.from(document.querySelectorAll("button"))
                        .filter(e => e.offsetParent !== null && e.innerText.includes("Save changes"));
                    if (btns.length > 1) btns[1].click();
                    else if (btns.length === 1) btns[0].click();
                }''')
                await asyncio.sleep(3)
                logger.info("  Cappings נשמרו ✓")
            except Exception as e:
                logger.warning(f"  Save cappings: {e}")

            await next_step(page)
            logger.info("שלב 4 הושלם ✓")

            # ── שלב 5: Overview + Submit ──────────────────────────────────────
            logger.info("שלב 5 – Overview ושליחה")
            await asyncio.sleep(2)
            await page.screenshot(path="overview.png")

            # קח את ה-ID מה-URL ונווט ישירות לדף finalize
            campaign_id = page.url.split("id=")[-1].split("&")[0]
            finalize_url = f"https://adcash.myadcash.com/campaign/advanced/complete/finalize?id={campaign_id}&validate=1"
            logger.info(f"  Finalize: {finalize_url}")
            await page.goto(finalize_url, timeout=30000)
            await asyncio.sleep(5)
            await page.screenshot(path="campaign_created.png")
            logger.info(f"✅ קמפיין נוצר! URL: {page.url}")
            if "dashboard" in page.url:
                logger.info("✅ קמפיין אושר ומופיע ברשימת הקמפיינים!")

        except Exception as e:
            logger.error(f"שגיאה: {e}")
            await page.screenshot(path="error.png")
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(create_campaign())
