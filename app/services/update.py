# app/services/update.py
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.search import (
    tavily_client,
    INDIA_ECOM_DOMAINS,
    _extract_price_from_text,
    _price_str_to_float,
    _platform_from_url,
)


def _get_image_aggressively(url: str, result: Dict[str, Any], search_images: List[Any]) -> Optional[str]:
    """
    ✅ NEW HELPER - Aggressively extract image from multiple sources:
    1. Per-result images (if Tavily provides them in the result)
    2. Top-level search images
    3. Extract images directly from the product page
    """
    images = result.get("images") or []
    if isinstance(images, list) and images:
        img0 = images[0]
        if isinstance(img0, str):
            return img0
        elif isinstance(img0, dict):
            img_url = img0.get("url")
            if img_url:
                return img_url

    if search_images:
        img = search_images[0]  
        if isinstance(img, str):
            return img
        elif isinstance(img, dict):
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
                elif isinstance(first_img, dict):
                    img_url = first_img.get("url")
                    if img_url:
                        return img_url
    except Exception:
        pass

    return None


def find_lowest_price_offer(query: str) -> Dict[str, Any]:
    """
    Use Tavily (restricted to INDIA_ECOM_DOMAINS from .env)
    and return the single lowest-priced offer we can detect.
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
        return {"success": False, "reason": f"tavily_error:{e}", "offer": None}

    results: List[Dict[str, Any]] = search_result.get("results") or []
    search_images: List[Any] = search_result.get("images") or []  

    if not results:
        return {"success": False, "reason": "no_results", "offer": None}

    best_offer = None
    best_price = None

    for r in results:
        url: str = r.get("url") or ""
        title: str = r.get("title") or query
        snippet: str = r.get("content") or ""
        raw_content: str = r.get("raw_content") or ""  

        text_for_price = f"{title} {snippet} {raw_content}"
        price_str: Optional[str] = _extract_price_from_text(text_for_price)

        if not price_str:
            try:
                extract_resp = tavily_client.extract(urls=[url], include_images=False)
                extracted = extract_resp.get("results") or []
                if extracted:
                    page_content = extracted[0].get("content") or ""
                    price_str = _extract_price_from_text(page_content)
            except Exception:
                pass

        if not price_str:
            continue

        price_num = _price_str_to_float(price_str)
        if price_num is None:
            continue

        image_url = _get_image_aggressively(url, r, search_images)

        platform = _platform_from_url(url)

        offer = {
            "productName": title,
            "price_str": price_str,
            "price_num": price_num,
            "platform": platform,
            "deepLink": url,
            "imageUrl": image_url,
        }

        if best_price is None or price_num < best_price:
            best_price = price_num
            best_offer = offer

    if best_offer is None:
        return {"success": False, "reason": "no_priced_offer", "offer": None}

    return {"success": True, "reason": "ok", "offer": best_offer}


def update_product_lowest_price(
    db: Session,
    product_id: int,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update a single Product row:
      - Tavily lowest price for (query or product.name)
      - currentPrice, lastLowestPrice, isPriceDropped, imageUrl, deepLink, platform
    """
    product = db.get(Product, product_id)
    if not product:
        return {"success": False, "reason": "product_not_found"}

    search_query = query or product.name
    result = find_lowest_price_offer(search_query)
    if not result["success"]:
        return result

    offer = result["offer"]
    new_price = offer["price_num"]

    old_last_lowest = product.last_lowest_price

    product.current_price = new_price

    if old_last_lowest is None:
        product.last_lowest_price = new_price
        product.is_price_dropped = False
    else:
        if new_price < old_last_lowest:
            product.last_lowest_price = new_price
            product.is_price_dropped = True
        else:
            product.is_price_dropped = False

    product.image_url = offer["imageUrl"]
    product.deep_link = offer["deepLink"]
    product.platform = offer["platform"]

    db.add(product)
    db.commit()
    db.refresh(product)

    return {
        "success": True,
        "reason": "updated",
        "product_id": product_id,
        "offer": offer,
    }


def refresh_all_products_lowest_prices(db: Session) -> Dict[str, Any]:
    """
    For each product in table:
      - search Tavily for the lowest price
      - update:
          currentPrice
          lastLowestPrice
          isPriceDropped
          imageUrl
          deepLink
          platform
    """
    products = db.query(Product).all()

    updated = 0
    failed: List[Dict[str, Any]] = []

    for product in products:
        query = product.name

        result = find_lowest_price_offer(query)
        if not result["success"]:
            failed.append(
                {
                    "pid": product.pid,
                    "name": product.name,
                    "reason": result.get("reason", "unknown"),
                }
            )
            continue

        offer = result["offer"]
        new_price = offer["price_num"]

        old_last_lowest = product.last_lowest_price

        product.current_price = new_price

        if old_last_lowest is None:
            product.last_lowest_price = new_price
            product.is_price_dropped = False
        else:
            if new_price < old_last_lowest:
                product.last_lowest_price = new_price
                product.is_price_dropped = True
            else:
                product.is_price_dropped = False

        product.image_url = offer["imageUrl"]
        product.deep_link = offer["deepLink"]
        product.platform = offer["platform"]

        db.add(product)
        updated += 1

    db.commit()

    return {
        "success": True,
        "total_products": len(products),
        "updated_count": updated,
        "failed": failed,
    }
