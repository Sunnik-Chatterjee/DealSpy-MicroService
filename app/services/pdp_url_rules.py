# app/services/pdp_url_rules.py
from urllib.parse import urlparse, urljoin, parse_qs

def is_probable_pdp(url: str) -> bool:
    """
    Heuristic PDP rules for top Indian e-comm sites.
    Rejects search/browse pages and prefers canonical PDP patterns.
    """
    if not url:
        return False
    u = urlparse(url)
    host = (u.netloc or "").lower()
    path = (u.path or "").lower()
    query = (u.query or "").lower()

    # Common search/browse rejections
    if any(k in path for k in ["/search", "/s", "/catalog", "/browse", "/category", "/collections", "/results"]):
        return False
    if any(k in query for k in ["q=", "query=", "search="]):
        return False

    # Domain patterns
    if "amazon." in host:
        # /dp/ or /gp/product/
        return ("/dp/" in path) or ("/gp/product/" in path)
    if "flipkart." in host:
        # /p/itm..., or /p/ with "-mobile" in slug
        return path.startswith("/p/itm") or ("/p/" in path and "-mobile" in path)
    if "reliancedigital." in host:
        return path.startswith("/p/")
    if "croma." in host:
        return path.startswith("/p/")
    if "vijaysales." in host:
        return "/product/" in path
    if "apple." in host:
        return "/shop/buy-iphone/" in path

    # Generic fallback: PDP often has an id-like slug (digits or sku)
    return any(seg.isdigit() for seg in path.strip("/").split("/"))

def is_probable_pdp(url: str) -> bool:
    if not url:
        return False
    u = urlparse(url)
    host = (u.netloc or "").lower()
    path = (u.path or "").lower()
    query = (u.query or "").lower()

    # Reject obvious non-PDP
    if any(k in path for k in ["/search", "/s", "/catalog", "/browse", "/category",
                               "/collections", "/results", "/product-reviews"]):
        return False
    if any(k in query for k in ["q=", "query=", "search="]):
        return False

    # PDP patterns
    if "amazon." in host:
        return ("/dp/" in path) or ("/gp/product/" in path)
    if "flipkart." in host:
        return path.startswith("/p/itm") or ("/p/" in path)
    if "reliancedigital." in host:
        return path.startswith("/p/")
    if "croma." in host:
        return path.startswith("/p/")
    if "vijaysales." in host:
        return "/product/" in path
    if "apple." in host:
        return "/shop/buy-iphone/" in path

    return any(seg.isdigit() for seg in path.strip("/").split("/"))

def normalize_pdp_from_review_or_search(domain: str, url: str, html: str | None) -> str | None:
    """
    Convert review/search URLs to their PDP when possible without heavy crawling.
    """
    u = urlparse(url)
    host = (u.netloc or "").lower()
    path = (u.path or "").lower()
    qs   = parse_qs(u.query or "")

    # Flipkart review → PDP using pid
    if "flipkart." in host and "/product-reviews/" in path:
        pid = (qs.get("pid") or [None])[0]
        if pid:
            # canonical minimal PDP form works on Flipkart:
            # /p/ with pid param; if it redirects that’s fine
            return f"https://www.flipkart.com/p/itm{pid.lower()[:6]}?pid={pid}"
        # fallback: let the search-page parser handle (if provided) elsewhere
        return None

    # Amazon search → leave to search-to-PDP fallback
    # Others handled by fallback parser
    return None
