# app/services/update_product.py

from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.tavily_search import resolve_urls_all_sites
from app.services.fetch_http import fetch_html
from app.services.extract_mistral import extract_from_html
from app.core.config import get_india_domains


def _choose_lowest(prices: List[Tuple[str, float, str]]) -> Optional[Tuple[str, float, str]]:
    """
    prices: list of (domain, price, deep_link)
    returns the tuple with minimum price or None.
    """
    if not prices:
        return None
    return min(prices, key=lambda x: x[1])


def update_single_product_lowest(
    db: Session,
    pid: int,
    domains: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    For the given product id:
      - search on India-specific domains (or provided 'domains')
      - fetch & extract price from each found PDP
      - choose today's lowest price and update the product row with:
            currentPrice       := today's lowest market price
            deepLink           := deeplink of the winning domain
            isPriceDropped     := True iff today's lowest < yesterday's currentPrice
            lastLowestPrice    := yesterday's currentPrice (previous value)
    Returns a summary dict with details per domain for observability.
    """
    product = db.query(Product).filter(Product.pid == pid).first()
    if not product:
        return {"pid": pid, "status": "not_found"}

    query = product.name
    domains = domains or get_india_domains()

    # 1) Resolve a PDP URL for each domain
    domain_to_url = resolve_urls_all_sites(query, domains)

    # 2) Fetch + extract per domain
    found: List[Tuple[str, float, str]] = []
    details: List[Dict[str, Any]] = []
    for domain, url in domain_to_url.items():
        if not url:
            details.append({"domain": domain, "status": "no_url"})
            continue

        code, html = fetch_html(url)
        if code != 200 or not html:
            details.append({"domain": domain, "status": f"http_{code}", "url": url})
            continue

        data = extract_from_html(html, url)
        price = data.get("price_value")
        link = data.get("deep_link") or url

        if price is None:
            details.append({"domain": domain, "status": "no_price", "url": url})
            continue

        found.append((domain, float(price), link))
        details.append({"domain": domain, "status": "ok", "price": float(price), "url": link})

    # 3) Choose today's lowest INR price among India domains
    best = _choose_lowest(found)
    if not best:
        return {"pid": pid, "status": "no_price_any_domain", "details": details}

    best_domain, best_price, best_link = best

    # ===== PRICE-UPDATE RULES YOU REQUESTED =====
    old_price = product.currentPrice  # yesterday's current lowest (may be None first time)

    # currentPrice is always today's lowest market price
    product.currentPrice = best_price
    product.deepLink = best_link

    if old_price is None:
        # First-time initialization
        product.isPriceDropped = False
        product.lastLowestPrice = best_price
    else:
        # isPriceDropped: True iff today's lowest < yesterday's currentPrice
        product.isPriceDropped = best_price < old_price
        # lastLowestPrice stores yesterday's price for next comparison
        product.lastLowestPrice = old_price
    # ============================================

    db.add(product)
    db.commit()
    db.refresh(product)

    return {
        "pid": pid,
        "status": "ok",
        "selected_domain": best_domain,
        "currentPrice": product.currentPrice,
        "lastLowestPrice": product.lastLowestPrice,
        "isPriceDropped": product.isPriceDropped,
        "deepLink": product.deepLink,
        "details": details,  # per-domain attempts (debug/observability)
    }


def update_products_lowest(
    db: Session,
    pids: List[int],
    domains: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Batch version: update multiple product ids in one call.
    Returns a summary with per-pid results.
    """
    results: List[Dict[str, Any]] = []
    updated = failed = 0

    for pid in pids:
        res = update_single_product_lowest(db, pid, domains)
        results.append(res)
        if res.get("status") == "ok":
            updated += 1
        else:
            failed += 1

    return {
        "updated": updated,
        "failed": failed,
        "results": results,
    }
