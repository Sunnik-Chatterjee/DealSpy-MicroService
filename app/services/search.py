# app/services/search.py

import re
import requests
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from tavily import TavilyClient

from app.core.config import get_settings, get_india_domains

settings = get_settings()
INDIA_ECOM_DOMAINS = get_india_domains()
tavily_client = TavilyClient(api_key=settings.tavily_api_key)

PRICE_PATTERNS = [
    re.compile(r"₹\s*([0-9][0-9,]*(?:\.[0-9]{2})?)"),
    re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{2})?)"),
    re.compile(r"([0-9][0-9,]*(?:\.[0-9]{2})?)\s*INR"),
    re.compile(r"Rs\.?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)"),
]

ALLOWED_PLATFORMS = {
    "amazon", "flipkart", "croma", "reliance digital", "reliancedigital",
    "myntra", "ajio",
    "meesho", "tatacliq", "shopclues", "pepperfry", "nykaa", "firstcry", "grofers"
}

ACCESSORY_KEYWORDS = [
    "case", "cover", "back cover", "tempered", "screen guard", "screen protector",
    "glass protector", "charger", "cable", "adapter", "strap", "band",
    "earbud", "earbuds", "earphone", "earphones", "headphone", "headphones",
    "power bank", "stand", "holder", "mount",
]

KNOWN_BRANDS = [
    "Apple", "Samsung", "OnePlus", "Xiaomi", "Redmi", "Realme", "Oppo", "Vivo", "Motorola",
    "Nike", "Adidas", "Puma", "Reebok", "Fila",
    "Sony", "LG", "Panasonic", "Whirlpool", "Bosch",
    "HP", "Dell", "Lenovo", "Asus", "Acer",
    "Levi's", "H&M", "Zara", "Allen Solly", "Peter England",
]


# ---------- price & platform helpers ----------

def _extract_price_from_text(text: str) -> Optional[str]:
    """Extract price from text with improved pattern matching."""
    if not text:
        return None

    for pat in PRICE_PATTERNS:
        m = pat.search(text)
        if m:
            price_part = m.group(1) if m.lastindex else m.group(0)
            return price_part.strip()
    return None


def _price_str_to_float(price_str: str) -> Optional[float]:
    """Convert price string to float, handling Indian number format."""
    if not price_str:
        return None

    digits = re.sub(r"[^\d.,]", "", price_str)
    digits = digits.replace(",", "")

    if not digits:
        return None

    try:
        price = float(digits)
        # sanity check: 1k to 10 lakh
        if 1000 <= price <= 1000000:
            return price
        return None
    except ValueError:
        return None


def _platform_from_url(url: str) -> str:
    """Return normalized platform name based on domain."""
    host = urlparse(url).netloc.lower().replace("www.", "")

    if not host:
        return "unknown"

    if "amazon." in host:
        return "amazon"
    if "flipkart." in host:
        return "flipkart"
    if "myntra." in host:
        return "myntra"
    if "ajio." in host:
        return "ajio"
    if "meesho." in host:
        return "meesho"
    if "tatacliq." in host:
        return "tatacliq"
    if "shopclues." in host:
        return "shopclues"
    if "pepperfry." in host:
        return "pepperfry"
    if "nykaa." in host:
        return "nykaa"
    if "firstcry." in host:
        return "firstcry"
    if "grofers." in host or "blinkit." in host:
        return "grofers"
    if "croma." in host:
        return "croma"
    if "reliancedigital." in host or "reliance." in host:
        return "reliance digital"

    return host.split(".")[0]


def _looks_like_product_url(url: str) -> bool:
    """Validate if URL is a product page."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    host = parsed.netloc.lower()

    # Amazon: /dp/, /gp/product/, /product/
    if "amazon" in host:
        return any(p in path for p in ["/dp/", "/gp/product/", "/product/"])

    # Flipkart: /p/ or product ID pattern
    if "flipkart" in host:
        return "/p/" in path or bool(re.search(r"/[a-z0-9-]+-p-[a-z0-9]+", path))

    # Myntra: /buy/ or product ID
    if "myntra" in host:
        return "/buy/" in path or bool(re.search(r"/\d+/buy", path))

    # AJIO: /p/ or /product/
    if "ajio" in host:
        return "/p/" in path or "/product/" in path

    # Croma: /p/ or /product/
    if "croma" in host:
        return "/p/" in path or "/product/" in path

    # Reliance Digital: /product/ or /pd/
    if "reliancedigital" in host:
        return "/product/" in path or "/pd/" in path

    # For other known platforms, be lenient: rely on title/snippet & price filters
    if any(p in host for p in [
        "meesho", "tatacliq", "shopclues", "pepperfry", "nykaa", "firstcry", "grofers", "blinkit"
    ]):
        return True

    # Generic fallback for unknown hosts
    return any(p in path for p in ["/product/", "/p/", "/item/", "/dp/"])


# ---------- query/text helpers ----------

def _extract_core_product_terms(query: str) -> List[str]:
    """Extract core product terms for matching (e.g., 'iphone 14' -> ['iphone', '14'])."""
    q = query.lower().strip()

    stop_words = ["buy", "online", "india", "price", "best", "cheapest", "latest"]
    for word in stop_words:
        q = re.sub(r"\b" + word + r"\b", "", q)

    q = re.sub(r"\s+", " ", q).strip()
    terms = q.split()
    return [t for t in terms if len(t) >= 2]


def _normalize_for_match(text: str) -> str:
    """Normalize text for matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _is_accessory_text(text: str) -> bool:
    """Check if text contains accessory keywords."""
    lower = text.lower()
    for kw in ACCESSORY_KEYWORDS:
        if re.search(r"\b" + kw + r"\b", lower):
            return True
    return False


def _product_matches_query(title: str, snippet: str, query: str) -> bool:
    """Check if product matches the search query accurately."""
    combined = f"{title or ''} {snippet or ''}".lower()

    if _is_accessory_text(combined):
        return False

    core_terms = _extract_core_product_terms(query)
    if not core_terms:
        return False

    norm_combined = _normalize_for_match(combined)

    matches = 0
    for term in core_terms:
        norm_term = _normalize_for_match(term)
        if norm_term in norm_combined:
            matches += 1

    match_ratio = matches / len(core_terms) if core_terms else 0
    return match_ratio >= 0.6


def _extract_brand_from_title(title: str) -> Optional[str]:
    """Extract brand from product title."""
    if not title:
        return None

    title_lower = title.lower()
    for brand in KNOWN_BRANDS:
        if re.search(r"\b" + brand.lower() + r"\b", title_lower):
            return brand

    words = title.split()
    if words and words[0][0].isupper():
        return words[0]

    return None


# ---------- image helpers ----------

def _is_valid_product_image(img_url: str) -> bool:
    """Light validation to avoid obvious non-product images."""
    if not img_url:
        return False

    img_lower = img_url.lower()

    reject_patterns = [
        "logo", "icon", "sprite", "banner", "button", "badge", "avatar",
        "flipkart-plus", "prime-logo", "assured", "fk-p-linchpin"
    ]
    if any(pat in img_lower for pat in reject_patterns):
        return False

    return any(ext in img_lower for ext in [".jpg", ".jpeg", ".png", ".webp"])


def _fetch_image_from_url_direct(url: str) -> Optional[str]:
    """Directly fetch and scrape product page for image - last resort."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        platform = _platform_from_url(url).lower()

        # 1) og:image – most sites set this correctly
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            img_url = urljoin(url, og["content"])
            return img_url

        # 2) Platform-specific tweaks

        # Amazon
        if "amazon" in platform:
            selectors = [
                {"id": "landingImage"},
                {"id": "imgBlkFront"},
                {"class": "a-dynamic-image"},
            ]
            for selector in selectors:
                img = soup.find("img", selector)
                if not img:
                    continue
                img_url = (
                    img.get("src")
                    or img.get("data-old-hires")
                    or img.get("data-a-dynamic-image")
                )
                if not img_url:
                    continue

                if img_url.startswith("{"):
                    try:
                        import json
                        data = json.loads(img_url)
                        if isinstance(data, dict) and data:
                            img_url = list(data.keys())[0]
                    except Exception:
                        pass

                if img_url and _is_valid_product_image(img_url):
                    return img_url

            for img in soup.find_all("img"):
                src = img.get("src", "") or ""
                if "m.media-amazon.com/images" in src or "images-na.ssl-images-amazon" in src:
                    if _is_valid_product_image(src):
                        return src

        # Flipkart
        if "flipkart" in platform:
            def _get_src(img_tag):
                src = img_tag.get("src") or img_tag.get("data-src")
                if not src:
                    srcset = img_tag.get("srcset")
                    if srcset:
                        first = srcset.split(",")[0].strip().split(" ")[0]
                        src = first
                return src

            for img in soup.find_all("img"):
                src = _get_src(img)
                if src and "rukminim" in src and _is_valid_product_image(src):
                    return src

        # 3) Generic fallback: any image that looks like a product
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if not src:
                srcset = img.get("srcset")
                if srcset:
                    src = srcset.split(",")[0].strip().split(" ")[0]
            if not src:
                continue

            img_url = urljoin(url, src)
            if _is_valid_product_image(img_url):
                return img_url

    except Exception:
        return None

    return None


def _extract_image_from_result(result: Dict[str, Any], url: str) -> Optional[str]:
    """Extract product image with multiple fallback strategies."""
    platform = _platform_from_url(url).lower()

    # 1) Try images field from Tavily search result
    images = result.get("images", [])
    if images:
        best = None
        for img in images:
            img_url = img if isinstance(img, str) else img.get("url")
            if not img_url:
                continue

            if platform == "flipkart":
                if "flipkart-plus" in img_url or "fk-p-linchpin" in img_url:
                    continue
                if "rukminim" in img_url:
                    return img_url

            if _is_valid_product_image(img_url) and best is None:
                best = img_url

        if best:
            return best

    # 2) Try Tavily extract endpoint
    try:
        extract_resp = tavily_client.extract(
            urls=[url],
            include_images=True,
        )
        for page in extract_resp.get("results", []):
            page_images = page.get("images", [])
            best = None
            for img in page_images:
                img_url = img if isinstance(img, str) else img.get("url")
                if not img_url:
                    continue

                if platform == "flipkart":
                    if "flipkart-plus" in img_url or "fk-p-linchpin" in img_url:
                        continue
                    if "rukminim" in img_url:
                        return img_url

                if _is_valid_product_image(img_url) and best is None:
                    best = img_url

            if best:
                return best

            raw = page.get("raw_content") or ""
            if raw and "amazon" in platform:
                m = re.search(r"https://m\.media-amazon\.com/images/I/[^\s\"']+", raw)
                if m and _is_valid_product_image(m.group(0)):
                    return m.group(0)
            if raw and "flipkart" in platform:
                m = re.search(r"https://rukminim[^\"']+\.(?:webp|jpg|jpeg|png)", raw)
                if m and _is_valid_product_image(m.group(0)):
                    return m.group(0)
    except Exception:
        pass

    # 3) Final fallback: direct scraping
    return _fetch_image_from_url_direct(url)


# ---------- main search ----------

def search_products_sorted(query: str, limit: int = 15) -> Dict[str, Any]:
    """
    Search for products with accurate matching and proper image extraction.
    """

    enhanced_query = f"{query} price buy online India"

    # ensure multi-platform coverage
    CORE_DOMAINS = ["amazon.in", "flipkart.com", "myntra.com", "ajio.com"]

    all_results: List[Dict[str, Any]] = []

    for domain in CORE_DOMAINS:
        try:
            res: Dict[str, Any] = tavily_client.search(
                query=enhanced_query,
                search_depth="advanced",
                topic="general",
                max_results=8,
                include_answer=False,
                include_raw_content=True,
                include_images=True,
                include_domains=[domain],
                use_cache=False,
            )
            all_results.extend(res.get("results") or [])
        except Exception as e:
            print(f"⚠️ Tavily search failed for domain {domain}: {e}")
            continue

    results: List[Dict[str, Any]] = all_results

    if not results:
        return {
            "success": False,
            "message": f"No results found for '{query}'",
            "data": [],
        }

    valid_offers: List[Dict[str, Any]] = []
    seen_urls = set()

    for r in results:
        url: str = r.get("url") or ""

        if url in seen_urls:
            continue

        platform = _platform_from_url(url)
        if platform.lower() not in ALLOWED_PLATFORMS:
            continue

        if not _looks_like_product_url(url):
            continue

        title: str = r.get("title") or ""
        snippet: str = r.get("content") or r.get("raw_content") or ""

        if not _product_matches_query(title, snippet, query):
            continue

        text_for_price = f"{title} {snippet}"
        lower_text = text_for_price.lower()
        if any(keyword in lower_text for keyword in ["emi", "down payment", "monthly", "/month", "per month"]):
            if "no cost emi" not in lower_text and "full price" not in lower_text:
                continue

        price_str: Optional[str] = _extract_price_from_text(text_for_price)
        price_num = _price_str_to_float(price_str) if price_str else None

        if price_num is None:
            continue

        image_url = _extract_image_from_result(r, url)

        if not image_url:
            print(f"⚠️ No image found for: {title[:80]}... from {platform}")
        else:
            print(f"✅ IMAGE for {platform}: {title[:40]}... -> {image_url}")

        if not image_url:
            combined_text = f"{snippet} {r.get('content', '')}"
            img_matches = re.findall(
                r'(https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))',
                combined_text,
                re.IGNORECASE
            )
            for img_match in img_matches:
                if _is_valid_product_image(img_match):
                    image_url = img_match
                    print(f"✅ Found image in text: {img_match[:60]}")
                    break

        brand = _extract_brand_from_title(title)

        valid_offers.append({
            "name": title,
            "brand": brand,
            "platform": platform,
            "currentPrice": price_num,
            "imageUrl": image_url,
            "deepLink": url,
            "_price_num": price_num,
        })

        seen_urls.add(url)

    if not valid_offers:
        return {
            "success": False,
            "message": f"No matching products found for '{query}'",
            "data": [],
        }

    valid_offers.sort(key=lambda o: o.get("_price_num") or float("inf"))
    valid_offers = valid_offers[:limit]

    data = [
        {
            "productName": str(o["name"]) if o["name"] else None,
            "brand": str(o["brand"]) if o["brand"] else None,
            "platform": str(o["platform"]) if o["platform"] else None,
            "price": float(int(o["currentPrice"])) if o["currentPrice"] is not None else None,
            "imageUrl": str(o["imageUrl"]) if o["imageUrl"] else None,
            "deepLink": str(o["deepLink"]) if o["deepLink"] else None,
        }
        for o in valid_offers
    ]

    return {
        "success": True,
        "message": f"Found {len(data)} products for '{query}'",
        "data": data,
    }
