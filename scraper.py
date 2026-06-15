import logging
import random
import re
import requests
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

logger = logging.getLogger(__name__)

SITE_URL = "https://konimbezol.co.il"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


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
    if any(k in slug for k in ["kitchen", "garlic", "steak", "peeler", "scale", "grinder", "pepper", "kitchenaid", "vacuum", "brush", "grill"]):
        return "מוצרי מטבח"
    if any(k in slug for k in ["car", "obd", "freshener", "seat"]):
        return "מוצרים לרכב"
    if any(k in slug for k in ["yoga", "pilates", "fitness", "gym", "sport", "bike", "cycling", "jump-rope", "tennis", "volleyball", "ski", "grip", "ab-roller", "resistance", "band", "knee"]):
        return "ספורט וכושר"
    if any(k in slug for k in ["lamp", "light", "lock", "home", "garden", "closet", "rfid"]):
        return "בית וגן"
    if any(k in slug for k in ["watch", "jewelry", "necklace"]):
        return "שעונים ותכשיטים"
    return "גאדג'טים"


def _resolve_affiliate_url(url: str) -> str | None:
    """Follow affiliate redirect to get the real AliExpress product URL."""
    try:
        r = requests.get(url, allow_redirects=True, timeout=12, headers=HEADERS)
        final = r.url
        if "aliexpress.com/item/" in final:
            return final
    except Exception:
        pass
    return None


async def _get_aliexpress_stats(ali_url: str, page) -> dict:
    """Scrape purchase count and rating from AliExpress product page."""
    stats = {"orders": None, "rating": None}
    try:
        await page.goto(ali_url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(4000)
        body = await page.inner_text("body")

        # Orders: "1000+ sold", "2.3K+ sold", "10K+ sold", "500 orders"
        orders_match = re.search(
            r"([\d,]+(?:\.\d+)?[Kk]?\+?)\s*(?:sold|orders|הזמנות|נמכרו)",
            body, re.IGNORECASE
        )
        if orders_match:
            raw = orders_match.group(1).replace(",", "").strip()
            # Normalize: 2.3K -> 2300, 10K -> 10000
            if raw.lower().endswith("k"):
                num = float(raw[:-1]) * 1000
                stats["orders"] = f"{int(num):,}"
            else:
                stats["orders"] = raw

        # Rating: look for X.X pattern near "rating" or standalone 4.x/5.0
        rating_match = re.search(
            r"\b([4-5]\.\d)\b(?:[^\n]{0,30}(?:rating|stars|דירוג|כוכב))?",
            body, re.IGNORECASE
        )
        if not rating_match:
            # fallback: any 4.x or 5.0 number
            rating_match = re.search(r"\b([4-5]\.\d)\b", body)
        if rating_match:
            stats["rating"] = rating_match.group(1)

    except Exception as e:
        logger.debug(f"AliExpress stats fetch failed: {e}")
    return stats


def _clean_name(name: str) -> str:
    """Remove 'ביקורת/סקירת/המלצת' prefixes that appear in site page titles."""
    prefixes = ["ביקורת", "סקירת", "המלצת", "ביקורת:", "סקירה:", "Review:"]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):].strip(" :-–")
    return name.strip()


def _clean_feature(text: str) -> str:
    """Clean feature text: remove slashes, extra whitespace, fix formatting."""
    text = text.replace("/", "").replace("\\", "").replace("|", "")
    text = " ".join(text.split())  # normalize whitespace
    return text.strip(" :-–•·")


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
        name = _clean_name(name)

        image_url = await page.get_attribute('meta[property="og:image"]', "content")
        if not image_url:
            image_url = await page.get_attribute('meta[name="twitter:image"]', "content")

        # Extract feature bullets — look for <li> items in the product content
        features = []
        try:
            li_texts = await page.eval_on_selector_all(
                "li",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 5 && t.length < 150)"
            )
            skip_words = [
                "login", "cart", "menu", "home", "search", "privacy", "terms",
                "כל הקטגוריות", "דף הבית", "עגלה", "חיפוש", "התחבר", "הרשם",
                "צור קשר", "אודות", "מוצרים לרכב", "אופנה וסטייל", "מוצרי מטבח",
                "ספורט וכושר", "בית וגן", "שעונים ותכשיטים", "גאדג'טים",
                "מוצרים למטבח", "מוצרים לבית", "מוצרים לספורט", "חזרה",
                "קנה עכשיו", "הוסף לעגלה", "רכישה", "קניה", "מחיר"
            ]
            name_words = set((name or "").lower().split())
            for t in li_texts:
                t = t.strip().replace("\n", " ")
                cleaned = _clean_feature(t)
                if not cleaned or len(cleaned) < 10:
                    continue
                # Skip nav/breadcrumb/category items
                if any(x in cleaned for x in skip_words):
                    continue
                # Skip items that are mostly the product name
                cleaned_words = set(cleaned.lower().split())
                overlap = len(cleaned_words & name_words)
                if overlap >= 3 and len(cleaned_words) <= 5:
                    continue
                # Split at comma/dash and take first meaningful part
                for sep in ["–", "-", ",", ";"]:
                    if sep in cleaned:
                        parts = [p.strip() for p in cleaned.split(sep) if len(p.strip()) > 8]
                        if parts:
                            cleaned = parts[0]
                            break
                if 8 < len(cleaned) < 50:
                    features.append(cleaned)
                if len(features) >= 5:
                    break
        except Exception:
            pass

        # Fallback: extract from description
        if not features:
            desc = await page.get_attribute('meta[property="og:description"]', "content") or ""
            for line in desc.split("–"):
                line = line.strip()
                if 8 < len(line) < 100:
                    features.append(line)
                if len(features) >= 5:
                    break

        return {
            "name": name,
            "features": features[:6],
            "aliexpress_link": ali_link,
            "image_url": image_url,
            "category": _category_from_url(url),
            "source_url": url,
            "orders": None,
            "rating": None,
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
        ctx = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await ctx.new_page()

        for url in target_urls:
            product = await scrape_product_async(url, page)
            if product:
                # Try to get AliExpress stats
                real_url = _resolve_affiliate_url(product["aliexpress_link"])
                if real_url:
                    stats = await _get_aliexpress_stats(real_url, page)
                    product["orders"] = stats["orders"]
                    product["rating"] = stats["rating"]
                    # Navigate back after AliExpress scrape
                    try:
                        await page.go_back(timeout=5000)
                    except Exception:
                        pass

                products.append(product)
                logger.info(f"  ✓ {product['name'][:55]} | orders={product['orders']} rating={product['rating']}")
            if len(products) >= count:
                break

        await browser.close()

    logger.info(f"Scraped {len(products)}/{count} products")
    return products[:count]
