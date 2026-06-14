import requests
from bs4 import BeautifulSoup
import logging
import random
import re

logger = logging.getLogger(__name__)

SITE_URL = "https://konimbezol.co.il"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

CATEGORIES = [
    "/category/gadgets",
    "/category/fashion",
    "/category/home-garden",
    "/category/sports",
    "/category/kitchen",
    "/category/car-products",
    "/category/jewelry-watches",
]


def get_all_product_urls() -> list[str]:
    urls = set()

    # Scrape homepage
    try:
        r = requests.get(SITE_URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/product/" in href:
                if href.startswith("http"):
                    urls.add(href)
                else:
                    urls.add(SITE_URL + href)
    except Exception as e:
        logger.warning(f"Homepage scrape failed: {e}")

    # Scrape category pages
    for cat in CATEGORIES:
        try:
            r = requests.get(SITE_URL + cat, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/product/" in href:
                    if href.startswith("http"):
                        urls.add(href)
                    else:
                        urls.add(SITE_URL + href)
        except Exception as e:
            logger.warning(f"Category {cat} scrape failed: {e}")

    return list(urls)


def scrape_product(url: str) -> dict | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        # Product name
        name = None
        for tag in ["h1", "h2"]:
            el = soup.find(tag)
            if el and el.get_text(strip=True):
                name = el.get_text(strip=True)
                break

        if not name:
            return None

        # AliExpress affiliate link - look for s.click.aliexpress.com links
        ali_link = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "aliexpress.com" in href or "s.click.aliexpress" in href or "ali" in href.lower():
                ali_link = href
                break

        # Also check onclick / data attributes
        if not ali_link:
            for btn in soup.find_all(["a", "button"], attrs=True):
                for attr_val in btn.attrs.values():
                    if isinstance(attr_val, str) and "aliexpress" in attr_val:
                        # Try to extract URL from attribute
                        match = re.search(r'https?://[^\s"\']+aliexpress[^\s"\']+', attr_val)
                        if match:
                            ali_link = match.group(0)
                            break

        if not ali_link:
            return None

        # Description - try to get meaningful text
        desc = None
        for sel in ["p.description", ".product-description", "article p", ".content p", "p"]:
            els = soup.select(sel)
            for el in els:
                text = el.get_text(strip=True)
                if len(text) > 30 and name[:10] not in text[:10]:
                    desc = text[:200]
                    break
            if desc:
                break

        # Price
        price = None
        for sel in [".price", "[class*='price']", "span.amount", ".product-price"]:
            el = soup.select_one(sel)
            if el:
                price_text = el.get_text(strip=True)
                if "₪" in price_text or "$" in price_text or any(c.isdigit() for c in price_text):
                    price = price_text
                    break

        # Image
        image_url = None
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]
        else:
            img = soup.find("img", src=True)
            if img:
                src = img["src"]
                if src.startswith("http"):
                    image_url = src
                elif src.startswith("//"):
                    image_url = "https:" + src

        # Category from URL
        category = "מוצר מומלץ"
        if "gadget" in url:
            category = "גאדג'ט חייב"
        elif "fashion" in url or "shoes" in url or "leggings" in url or "dress" in url or "skirt" in url or "jacket" in url:
            category = "אופנה וסטייל"
        elif "kitchen" in url or "garlic" in url or "steak" in url:
            category = "מטבח"
        elif "car" in url:
            category = "לרכב"
        elif "sport" in url:
            category = "ספורט"
        elif "home" in url or "garden" in url or "light" in url or "lamp" in url or "grill" in url or "lock" in url:
            category = "בית וגן"
        elif "watch" in url or "jewelry" in url:
            category = "שעונים ותכשיטים"

        return {
            "name": name,
            "description": desc,
            "price": price,
            "aliexpress_link": ali_link,
            "image_url": image_url,
            "category": category,
            "source_url": url,
        }

    except Exception as e:
        logger.warning(f"Failed to scrape {url}: {e}")
        return None


def get_products(count: int = 12) -> list[dict]:
    """Fetch and return `count` random products from the site."""
    urls = get_all_product_urls()
    if not urls:
        logger.error("No product URLs found")
        return []

    random.shuffle(urls)
    products = []
    for url in urls:
        product = scrape_product(url)
        if product:
            products.append(product)
        if len(products) >= count:
            break

    logger.info(f"Scraped {len(products)} products")
    return products
