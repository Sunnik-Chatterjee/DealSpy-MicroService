# app/services/search.py

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from tavily import TavilyClient
from app.core.config import get_settings, get_india_domains

settings = get_settings()
INDIA_ECOM_DOMAINS = get_india_domains()
tavily_client = TavilyClient(api_key=settings.tavily_api_key)

PRICE_PATTERNS = [
    re.compile(r"(₹\s?[0-9][0-9,]*)"),
    re.compile(r"(\$[0-9][0-9,]*)"),
    re.compile(r"([0-9][0-9,]*\s?INR)"),
]


def _extract_price_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    for pat in PRICE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).strip()
    return None


def _price_str_to_float(price_str: str) -> Optional[float]:
    if not price_str:
        return None
    digits = re.sub(r"[^\d.,]", "", price_str)
    digits = digits.replace(",", "")
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def _platform_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if not host:
        return "Unknown"
    if "amazon" in host:
        return "Amazon"
    if "flipkart" in host:
        return "Flipkart"
    if "myntra" in host:
        return "Myntra"
    if "ajio" in host:
        return "AJIO"
    if "croma" in host:
        return "Croma"
    if "reliancedigital" in host:
        return "Reliance Digital"
    return host


ACCESSORY_KEYWORDS = [
    "case",
    "cover",
    "back cover",
    "tempered",
    "screen guard",
    "screen protector",
    "glass",
    "protector",
    "charger",
    "cable",
    "adapter",
    "strap",
    "band",
    "earbud",
    "earbuds",
    "earphone",
    "earphones",
    "headphone",
    "headphones",
    "power bank",
]

ALLOWED_PLATFORMS = {"amazon", "flipkart", "croma", "reliance digital", "myntra", "ajio"}


def _main_phrase_from_query(query: str) -> str:
    """
    Extract core phrase from query:
    - 'iphone 14 128gb black' -> 'iphone 14'
    - 'tshirt' -> 'tshirt'
    """
    q = re.sub(r"\s+", " ", query.lower()).strip()
    tokens = q.split()
    if len(tokens) >= 2:
        return " ".join(tokens[:2])
    return q


def _normalize_for_match(text: str) -> str:
    """
    Normalize text for robust matching:
    - lowercase
    - remove all non-alphanumeric chars
    So 'T-Shirt', 't shirt', 'tshirt' all normalize to 'tshirt'.
    """
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _is_accessory_text(text: str) -> bool:
    """
    Simple accessory check using substring keywords.
    """
    lower = text.lower()
    for kw in ACCESSORY_KEYWORDS:
        if kw in lower:
            return True
    return False


def _looks_like_main_product(title: str, snippet: str, query: str) -> bool:
    """
    Strict classification:
    - must NOT look like an accessory
    - normalized title/snippet must contain normalized main phrase
      (handles tshirt / t-shirt / t shirt, iphone 14, etc.)
    """
    t = title or ""
    s = snippet or ""
    combined = f"{t} {s}"

    if _is_accessory_text(combined):
        return False

    main_phrase = _main_phrase_from_query(query)
    if not main_phrase:
        return True  

    norm_main = _normalize_for_match(main_phrase)
    norm_title = _normalize_for_match(t)
    norm_snippet = _normalize_for_match(s)

    if norm_main and norm_main not in norm_title and norm_main not in norm_snippet:
        return False

    return True


def _is_non_accessory(title: str, snippet: str) -> bool:
    """Relaxed version: only ensure it's not an accessory."""
    combined = f"{title or ''} {snippet or ''}"
    return not _is_accessory_text(combined)


def _get_image_from_result_or_search(
    result: Dict[str, Any],
    search_images: List[Any],
    index: int,
    url: str,  
) -> Optional[str]:
    """
    Try AGGRESSIVELY to pull an image for a product:
    1) Per-result images (if Tavily provides them)
    2) Top-level search images (round-robin)
    3) Extract images from the actual product page using Tavily extract
    """
 
    images = result.get("images") or []
    if isinstance(images, list) and images:
        img0 = images[0]
        if isinstance(img0, str):
            return img0
        if isinstance(img0, dict):
            img_url = img0.get("url")
            if img_url:
                return img_url

    if search_images:
        img = search_images[index % len(search_images)]
        if isinstance(img, str):
            return img
        if isinstance(img, dict):
            img_url = img.get("url")
            if img_url:
                return img_url
    try:
        extract_resp = tavily_client.extract(
            urls=[url],
            include_images=True 
        )
        extracted = extract_resp.get("results") or []
        if extracted:
            page_images = extracted[0].get("images") or []
            if isinstance(page_images, list) and page_images:
                first_img = page_images[0]
                if isinstance(first_img, str):
                    return first_img
                if isinstance(first_img, dict):
                    img_url = first_img.get("url")
                    if img_url:
                        return img_url
    except Exception:
        pass

    return None

def search_products_sorted(query: str, limit: int = 15) -> Dict[str, Any]:
    """
    Returns MULTIPLE offers sorted by price (ascending) when possible.

    - If price is found -> sorted by price.
    - If price is not found -> still included, but shown after priced items.
    - Always tries to return *some* results for every search.
    """

    try:
        search_result: Dict[str, Any] = tavily_client.search(
            query=query,
            search_depth="basic",                       
            topic="general",
            max_results=5,       
            include_answer=False,
            include_raw_content=True,                 
            include_images=True,                       
            include_domains=INDIA_ECOM_DOMAINS,
            use_cache=True,
        )
    except Exception as e:
        return {
            "success": False,
            "message": f"Tavily error for '{query}': {e}",
            "data": [],
        }

    results: List[Dict[str, Any]] = search_result.get("results") or []
    search_images: List[Any] = search_result.get("images") or []

    if not results:
        return {
            "success": False,
            "message": f"No search results found for '{query}'",
            "data": [],
        }

    strict_offers: List[Dict[str, Any]] = []
    fallback_offers: List[Dict[str, Any]] = []

    for r in results:
        url: str = r.get("url") or ""
        title: str = r.get("title") or query
        content: str = r.get("content") or ""
        raw_content: str = r.get("raw_content") or ""

        text_for_price = f"{title} {content} {raw_content}"
        price_str: Optional[str] = _extract_price_from_text(text_for_price)
        price_num = _price_str_to_float(price_str) if price_str else None

        platform = _platform_from_url(url)
        platform_lower = platform.lower()

        is_known_platform = any(key in platform_lower for key in [
            "amazon",
            "flipkart",
            "croma",
            "reliance",
            "myntra",
            "ajio",
        ])

        snippet_for_match = content or raw_content

        if _looks_like_main_product(title, snippet_for_match, query) and is_known_platform:
            bucket = strict_offers
        elif _is_non_accessory(title, snippet_for_match):
            bucket = fallback_offers
        else:
            continue

        image_url = _get_image_from_result_or_search(
            result=r,
            search_images=search_images,
            index=len(strict_offers) + len(fallback_offers),
            url=url,  
        )

        candidate = {
            "productName": title,
            "price_str": price_str,        
            "price_num": price_num,        
            "platform": platform,
            "deepLink": url,
            "imageUrl": image_url,
        }

        bucket.append(candidate)

    if not strict_offers and not fallback_offers:
        generic_offers: List[Dict[str, Any]] = []
        for idx, r in enumerate(results[:limit]):
            url: str = r.get("url") or ""
            title: str = r.get("title") or query
            content: str = r.get("content") or ""
            raw_content: str = r.get("raw_content") or ""

            text_for_price = f"{title} {content} {raw_content}"
            price_str: Optional[str] = _extract_price_from_text(text_for_price)
            price_num = _price_str_to_float(price_str) if price_str else None

            platform = _platform_from_url(url)

            image_url = _get_image_from_result_or_search(
                result=r,
                search_images=search_images,
                index=idx,
                url=url,  
            )

            generic_offers.append({
                "productName": title,
                "price_str": price_str,
                "price_num": price_num,
                "platform": platform,
                "deepLink": url,
                "imageUrl": image_url,
            })

        if not generic_offers:
            return {
                "success": False,
                "message": f"No offers found for '{query}'",
                "data": [],
            }

        combined = generic_offers
    else:
        combined = strict_offers + fallback_offers

    seen_links = set()
    unique_offers: List[Dict[str, Any]] = []
    for o in combined:
        link = o["deepLink"]
        if link in seen_links:
            continue
        seen_links.add(link)
        unique_offers.append(o)

    if not unique_offers:
        return {
            "success": False,
            "message": f"No unique offers found for '{query}'",
            "data": [],
        }

    def sort_key(o: Dict[str, Any]):
        price_num = o.get("price_num")
        return (0, price_num) if price_num is not None else (1, 0)

    unique_offers.sort(key=sort_key)
    unique_offers = unique_offers[:limit]

    data = [
        {
            "productName": o["productName"],
            "price": o["price_str"] or "Not found",  
            "platform": o["platform"],
            "deepLink": o["deepLink"],
            "imageUrl": o["imageUrl"],
        }
        for o in unique_offers
    ]

    return {
        "success": True,
        "message": f"Search Results for '{query}' (priced first, then others)",
        "data": data,
    }
