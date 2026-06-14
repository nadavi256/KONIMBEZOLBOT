import logging
import random
import re
import requests
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

logger = logging.getLogger(__name__)

SITE_URL = "https://konimbezol.co.il"


def get_all_product_urls() -> list[str]:
    try:
        r = requests.get(f"{SITE_URL}/sitemap.xml", timeout=15)
        urls = re.findall(
            r"<loc>(https://konimbezol\.co\.il/product/[^<]+)</loc>", r.text
        )
        logger.info(f"Found {len(urls)} product URLs in sitemap")
        return urls
    except Exception as e:
        logger.error(f"Sitemap fetch failed: {e}")
        return []


def _category_from_url(url: str) -> str:
    slug = url.split("/product/")[-1].lower()
    if any(k in slug for k in ["shoe", "sneaker", "legging", "jacket", "dress", "skirt", "adidas", "nike", "jordan"]):
        return "אופנה וסטייל"
    if any(k in slug for k in ["kitchen", "garlic", "steak", "peeler", "scale", "grinder", "pepper", "kitchenaid"]):
        return "מוצרי מטבח"
    if any(k in slug for k in ["car", "obd", "freshener", "seat"]):
        return "מוצרים לרכב"
    if any(k in slug for k in ["yoga", "pilates", "fitness", "gym", "sport", "bike", "cycling", "jump-rope", "tennis", "volleyball", "ski", "grip", "ab-roller", "resistance", "band", "knee"]):
        return "ספורט וכושר"
    if any(k in slug for k in ["lamp", "light", "grill", "lock", "home", "garden", "closet", "rfid"]):
        return "בית וגן"
    if any(k in slug for k in ["watch", "jewelry", "necklace"]):
        return "שעונים ותכשיטים"
    return "גאדג'טים"


async def scrape_product_async(url: str, page) -> dict | None:
    try:
        await page.goto(url, wait_until="networkidle", timeout=25000)
    except PWTimeout:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            logger.warning(f"Navigation failed for {url}: {e}")
            return None
    except Exception as e:
        logger.warning(f"Navigation failed for {url}: {e}")
        return None

    try:
        links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        ali_link = next(
            (l for l in links if "aliexpress.com" in l or "s.click.aliexpress" in l), None
        )
        if not ali_link:
            return None

        name = None
        if await page.query_selector("h1"):
            name = (await page.inner_text("h1")).strip()
        if not name:
            og_title = await page.get_attribute('meta[property="og:title"]', "content")
            name = og_title.strip() if og_title else None
        if not name:
            return None

        image_url = await page.get_attribute('meta[property="og:image"]', "content")
        if not image_url:
            image_url = await page.get_attribute('meta[name="twitter:image"]', "content")

        desc = await page.get_attribute('meta[property="og:description"]', "content")
        if not desc:
            desc = await page.get_attribute('meta[name="description"]', "content")
        if desc:
            desc = desc.strip()[:220]

        body_text = await page.inner_text("body")
        prices = re.findall(r"[₪\$]\s*\d+[\d.,]*", body_text)
        price = prices[0] if prices else None

        return {
            "name": name,
            "description": desc,
            "price": price,
            "aliexpress_link": ali_link,
            "image_url": image_url,
            "category": _category_from_url(url),
            "source_url": url,
        }

    except Exception as e:
        logger.warning(f"Parse error for {url}: {e}")
        return None


async def get_products(count: int = 12) -> list[dict]:
    urls = get_all_product_urls()
    if not urls:
        return []

    random.shuffle(urls)
    target_urls = urls[:min(count * 3, len(urls))]

    products = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(ignore_https_errors=True)
        page = await ctx.new_page()

        for url in target_urls:
            product = await scrape_product_async(url, page)
            if product:
                products.append(product)
                logger.info(f"  ✓ {product['name'][:55]}")
            if len(products) >= count:
                break

        await browser.close()

    logger.info(f"Scraped {len(products)}/{count} products")
    return products[:count]
