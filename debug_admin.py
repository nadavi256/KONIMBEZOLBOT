"""One-time debug script: explore the admin page structure."""
import asyncio
from playwright.async_api import async_playwright

ADMIN_URL = "https://konimbezol.co.il/admin/all-deals"
USERNAME = "nadavi256"
PASSWORD = "Nadavi256!0526732399"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await ctx.new_page()

        print(f"Navigating to {ADMIN_URL}...")
        await page.goto(ADMIN_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)
        print(f"URL after load: {page.url}")

        # Try login if form exists
        pwd = await page.query_selector("input[type='password']")
        if pwd:
            print("Login form detected — filling credentials...")
            for sel in ["input[type='email']", "input[type='text']", "input[name='username']"]:
                el = await page.query_selector(sel)
                if el:
                    await el.fill(USERNAME)
                    break
            await pwd.fill(PASSWORD)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(3000)
            print(f"After login URL: {page.url}")

        # Print page text
        body = await page.inner_text("body")
        print("\n=== PAGE TEXT (first 5000 chars) ===")
        print(body[:5000])

        # Find product links sorted by date
        links = await page.eval_on_selector_all(
            "a[href*='/product/']",
            "els => els.map(e => ({href: e.href, text: e.innerText.trim().substring(0,80)}))"
        )
        print(f"\n=== PRODUCT LINKS FOUND: {len(links)} ===")
        for l in links[:30]:
            print(f"  {l['text'][:60]} → {l['href']}")

        # Find any table or list structure
        rows = await page.eval_on_selector_all(
            "tr, [class*='row'], [class*='item'], [class*='deal'], [class*='product']",
            "els => els.slice(0,20).map(e => e.innerText.trim().substring(0,100))"
        )
        print(f"\n=== ROWS/ITEMS FOUND: {len(rows)} ===")
        for r in rows[:20]:
            if r:
                print(f"  {r}")

        await browser.close()

asyncio.run(main())
