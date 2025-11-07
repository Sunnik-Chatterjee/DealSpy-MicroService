# app/services/preview_search.py
from __future__ import annotations
from typing import Optional, Dict, Any, List, Tuple

from app.core.config import get_india_domains
from app.services.tavily_search import resolve_urls_all_sites
from app.services.fetch_http import fetch_html
from app.services.extract_mistral import extract_from_html
from app.services.pdp_url_rules import is_probable_pdp
from app.services.product_guards import (
    validate_query,
    looks_like_accessory,
    is_correct_variant,
    is_phone_category,
)
from app.services.price_utils import parse_price_strict, min_expected_price_for_query
from app.services.search_to_pdp_fallback import find_pdp_from_search_html


def _choose_lowest(prices: List[Tuple[str, float, str]]) -> Optional[Tuple[str, float, str]]:
    """Return (domain, price, deeplink) with the lowest price, or None if empty."""
    if not prices:
        return None
    return min(prices, key=lambda x: x[1])


def preview_lowest_by_name(query: str, domains: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Read-only flow:
      • Resolve candidate URLs per domain
      • Force PDP URLs (convert search/review pages → PDP when possible)
      • Extract strict phone price (with optional floor by model)
      • Reject accessories / wrong variants / wrong categories
      • Return the lowest price + deeplink + per-domain details
      • No DB writes
    """
    # 0) Early validation (avoid accessory-only queries, enforce model keyword)
    ok, reason = validate_query(query)
    if not ok:
        msg = (
            "Your query looks like an accessory. Please search a phone model (e.g., 'iPhone 15 128GB')."
            if reason == "query_is_accessory"
            else "Please include the phone model name (e.g., 'iPhone 15')."
        )
        return {
            "query": query,
            "status": reason,
            "message": msg,
            "details": [],
        }

    # 1) Domains (env-driven; see get_india_domains in app/core/config.py)
    domains = domains or get_india_domains()

    # 2) Resolve URLs (may still be search pages)
    domain_to_url = resolve_urls_all_sites(query, domains)

    # Optional floor only when we're confident (e.g., iPhone 15 → 30000); otherwise None
    min_floor = min_expected_price_for_query(query)

    found: List[Tuple[str, float, str]] = []
    details: List[Dict[str, Any]] = []
    sample_name: Optional[str] = None

    for domain, initial_url in domain_to_url.items():
        if not initial_url:
            details.append({"domain": domain, "status": "no_url"})
            continue

        url = initial_url

        # 3) If not a PDP, try to convert search page → PDP using lightweight HTML parse
        if not is_probable_pdp(url):
            code, html = fetch_html(url)
            if code == 200 and html:
                candidate = find_pdp_from_search_html(domain, html, url)
                if candidate and is_probable_pdp(candidate):
                    url = candidate
                else:
                    details.append({"domain": domain, "status": "not_pdp_url", "url": url})
                    continue
            else:
                details.append({"domain": domain, "status": f"http_{code}", "url": url})
                continue

        # 4) Fetch PDP page
        code, html = fetch_html(url)
        if code != 200 or not html:
            details.append({"domain": domain, "status": f"http_{code}", "url": url})
            continue

        # 5) Extract info from PDP
        data = extract_from_html(html, url)

        # Prefer canonical/og URL as a stable deeplink
        link = (data.get("canonical_url") or data.get("og_url") or data.get("deep_link") or url)

        name = (data.get("product_name") or data.get("title") or "").strip()
        category = (data.get("breadcrumbs") or data.get("category") or "").strip()
        raw_price = data.get("price_value") or data.get("price") or data.get("offer_price")

        # Strict price: parse & (optionally) apply floor (None = no floor)
        price = parse_price_strict(raw_price, min_floor=min_floor)

        if name and not sample_name:
            sample_name = name

        # 6) Guards
        if looks_like_accessory(name):
            details.append({"domain": domain, "status": "rejected_accessory", "url": link, "name": name})
            continue

        if not is_correct_variant(name, query):
            details.append({"domain": domain, "status": "variant_mismatch", "url": link, "name": name})
            continue

        if category and not is_phone_category(category):
            details.append({
                "domain": domain,
                "status": "category_mismatch",
                "url": link,
                "name": name,
                "category": category
            })
            continue

        if price is None:
            details.append({"domain": domain, "status": "no_price", "url": link, "name": name})
            continue

        # 7) Accept candidate
        found.append((domain, float(price), link))
        details.append({"domain": domain, "status": "ok", "price": float(price), "url": link, "name": name})

    # 8) Pick the winner or return a friendly no-deal message
    best = _choose_lowest(found)
    if not best:
        return {
            "query": query,
            "status": "no_deal",
            "message": "Can't find a better deal right now.",
            "product_name": sample_name,
            "details": details,
        }

    best_domain, best_price, best_link = best
    return {
        "query": query,
        "status": "ok",
        "product_name": sample_name,
        "selected_domain": best_domain,
        "currentPrice": best_price,
        "deepLink": best_link,
        "details": details,
    }
