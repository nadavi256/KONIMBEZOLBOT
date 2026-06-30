import logging
import random
import re
import requests
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

logger = logging.getLogger(__name__)

SITE_URL = "https://konimbezol.co.il"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


ADMIN_URL = "https://konimbezol.co.il/admin/all-deals"
ADMIN_USER = "nadavi256"
ADMIN_PASS = "Nadavi256!0526732399"


async def get_all_product_urls_from_admin(page) -> list[str]:
    """Scrape admin page to get ALL product URLs sorted by date (newest first)."""
    try:
        await page.goto(ADMIN_URL, wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(1500)

        # Login if needed
        pwd_input = await page.query_selector("input[type='password']")
        if pwd_input:
            for sel in ["input[type='email']", "input[type='text']", "input[name='username']"]:
                el = await page.query_selector(sel)
                if el:
                    await el.fill(ADMIN_USER)
                    break
            await pwd_input.fill(ADMIN_PASS)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(2500)

        # Extract product links in DOM order (= date order from admin page)
        links = await page.eval_on_selector_all(
            "a[href*='/product/']",
            "els => [...new Set(els.map(e => e.href))].filter(h => h.includes('/product/'))"
        )
        if links:
            logger.info(f"Admin page: found {len(links)} product URLs (date-sorted)")
            return links
    except Exception as e:
        logger.warning(f"Admin page scrape failed: {e}")
    return []


def get_all_product_urls_from_sitemap() -> list[str]:
    try:
        r = requests.get(f"{SITE_URL}/sitemap.xml", timeout=15)
        urls = re.findall(
            r"<loc>(https://konimbezol\.co\.il/product/[^<]+)</loc>", r.text
        )
        logger.info(f"Sitemap: found {len(urls)} product URLs")
        return urls
    except Exception as e:
        logger.error(f"Sitemap fetch failed: {e}")
        return []


def get_all_product_urls() -> list[str]:
    """Sync wrapper using sitemap (fallback). Admin page is used async in get_products."""
    return get_all_product_urls_from_sitemap()


def _category_from_product(url: str, name: str = "") -> str:
    slug = url.split("/product/")[-1].lower()
    text = slug + " " + name.lower()

    # אופנה וסטייל — ראשון, מאוד ספציפי
    if any(k in text for k in ["legging", "shoe", "sneaker", "jacket", "dress", "skirt",
                                 "adidas", "nike", "jordan", "shirt", "pants", "hoodie",
                                 "blouse", "shorts", "swimwear", "bikini", "socks",
                                 "underwear", "bra", "scrunch", "v-back", "sportswear",
                                 "אופנה", "בגד", "טייץ", "חולצה", "מכנסיים"]):
        return "אופנה וסטייל"

    # שעונים ותכשיטים
    if any(k in text for k in ["watch", "jewelry", "necklace", "bracelet", "ring",
                                 "earring", "pendant", "smartwatch", "שעון", "תכשיט"]):
        return "שעונים ותכשיטים"

    # ספורט וכושר
    if any(k in text for k in ["yoga", "pilates", "fitness", "gym", "sport", "bike",
                                 "cycling", "tennis", "racket", "volleyball", "badminton",
                                 "ski", "ab-roller", "resistance", "dumbbell", "barbell",
                                 "jump-rope", "treadmill", "ems", "muscle", "abs",
                                 "ספורט", "כושר", "אימון"]):
        return "ספורט וכושר"

    # מוצרים לרכב — מאוד ספציפי
    if any(k in text for k in ["car-", "-car", "obd", "dashcam", "tire", "steering",
                                 "windshield", "רכב"]):
        return "מוצרים לרכב"

    # גאדג'טים — לפני בית/מטבח כי "light" כללי מדי
    if any(k in text for k in ["flashlight", "torch", "headlamp", "led-light",
                                 "power-bank", "powerbank", "power bank", "anker", "baseus",
                                 "charger", "charging", "cable", "usb", "bluetooth",
                                 "speaker", "earphone", "headphone", "camera", "drone",
                                 "printer", "scanner", "keyboard", "mouse", "fan",
                                 "heater", "air", "purifier", "battery", "סוללה",
                                 "פנס", "גאדג'ט", "טעינה"]):
        return "גאדג'טים"

    # מוצרי מטבח
    if any(k in text for k in ["kitchen", "garlic", "steak", "peeler", "scale",
                                 "grinder", "pepper", "kitchenaid", "knife", "cutting",
                                 "chopper", "blender", "coffee", "mug", "pot", "pan",
                                 "broom", "mop", "cleaning", "vacuum", "brush", "grill",
                                 "food-storage", "food-bag", "seal", "zipper", "container",
                                 "freezer", "fridge", "reusable-bag",
                                 "מטבח", "סכין", "ניקוי", "מגב", "שקית מזון"]):
        return "מוצרי מטבח"

    # בית וגן — ספציפי, לא "home-" כללי (כדי שלא יתפוס home-charger וכד')
    if any(k in text for k in ["desk-lamp", "ceiling", "led-strip", "night-light",
                                 "door-lock", "smart-home", "garden", "closet", "wardrobe",
                                 "rfid", "shelf", "hanger", "curtain", "pillow", "blanket",
                                 "גן", "מדף", "ארון", "וילון", "כרית"]):
        return "בית וגן"

    # כלי עבודה
    if any(k in text for k in ["drill", "soldering", "soldering-iron", "wrench", "screwdriver",
                                 "saw", "hammer", "deko", "bosch", "stanley",
                                 "כלי-עבודה", "מברגה", "מלחם", "מקדחה"]):
        return "כלי עבודה"

    # מוצרים לילדים
    if any(k in text for k in ["kids", "child", "children", "baby", "toy", "toddler",
                                 "ילד", "ילדים", "תינוק", "צעצוע"]):
        return "מוצרים לילדים"

    return "גאדג'טים"


def _clean_aliexpress_url(url: str) -> str:
    """Strip tracking params — keep only the item ID."""
    m = re.search(r"aliexpress\.com/item/(\d+)\.html", url)
    if m:
        return f"https://www.aliexpress.com/item/{m.group(1)}.html"
    return url


def _resolve_affiliate_url(url: str) -> str | None:
    """Follow affiliate redirect to get the real AliExpress product URL."""
    try:
        r = requests.get(url, allow_redirects=True, timeout=12, headers=HEADERS)
        final = r.url
        if "aliexpress.com/item/" in final:
            return _clean_aliexpress_url(final)
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
        # Clean long tracking URLs — keep only item ID
        if "aliexpress.com/item/" in ali_link:
            ali_link = _clean_aliexpress_url(ali_link)

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
                "קנה עכשיו", "הוסף לעגלה", "רכישה", "קניה", "מחיר",
                # buying tips from website — not product features
                "seller rating", "tracking", "מדיניות החזרים", "ביקורות האחרונות",
                "דירוג המוכר", "בדקו את", "קראו את", "וודאו ש", "בדקו ש",
                "המשלוח כולל", "מעקב", "החזרה"
            ]
            # Also skip lines starting with a digit (numbered tips: "1 בדקו...")
            BUYING_TIP_RE = re.compile(r"^\d[\s\.]")
            name_words = set((name or "").lower().split())
            for t in li_texts:
                t = t.strip().replace("\n", " ")
                cleaned = _clean_feature(t)
                if not cleaned or len(cleaned) < 10:
                    continue
                # Skip nav/breadcrumb/category items
                if any(x in cleaned for x in skip_words):
                    continue
                if BUYING_TIP_RE.match(cleaned):
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
            "category": _category_from_product(url, name),
            "source_url": url,
            "orders": None,
            "rating": None,
        }

    except Exception as e:
        logger.warning(f"Parse error for {url}: {e}")
        return None


async def get_products(count: int = 12, exclude_urls: set | None = None) -> list[dict]:
    exclude_urls = exclude_urls or set()

    products = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await ctx.new_page()

        # Try admin page first (date-sorted, newest first)
        admin_urls = await get_all_product_urls_from_admin(page)
        if admin_urls:
            all_urls = admin_urls
        else:
            # Fallback: sitemap (no guaranteed date order)
            all_urls = get_all_product_urls_from_sitemap()

        if not all_urls:
            await browser.close()
            return []

        # Admin page is already newest-first — keep that order for unseen
        # Seen URLs go to the end (shuffled) as fallback
        unseen = [u for u in all_urls if u not in exclude_urls]
        seen   = [u for u in all_urls if u in exclude_urls]
        random.shuffle(seen)  # seen order doesn't matter, shuffle for variety
        target_urls = unseen + seen  # unseen kept in date order (newest first)
        logger.info(f"Targeting {len(target_urls)} URLs ({len(unseen)} unseen/new, {len(seen)} seen/recycled)")

        new_found = 0
        for url in target_urls:
            is_unseen = url not in exclude_urls
            # Stop only when we have enough AND we've moved past all unseen URLs
            if len(products) >= count and not is_unseen:
                break

            product = await scrape_product_async(url, page)
            if product:
                is_new = product["source_url"] not in exclude_urls
                tag = "🆕 NEW" if is_new else "♻️ recycled"
                products.append(product)
                if is_new:
                    new_found += 1
                logger.info(f"  {tag} {product['name'][:50]}")

        logger.info(f"Collected {len(products)} products ({new_found} new, {len(products)-new_found} recycled)")

        await browser.close()

    logger.info(f"Scraped {len(products)}/{count} products")
    return products[:count]
