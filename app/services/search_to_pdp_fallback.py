# app/services/search_to_pdp_fallback.py
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def find_pdp_from_search_html(domain: str, html: str, base_url: str) -> str | None:
    domain = (domain or "").lower()
    soup = BeautifulSoup(html or "", "html.parser")

    if "amazon." in domain:
        a = soup.select_one('a[href*="/dp/"]')
        if a and a.get("href"):
            return urljoin(base_url, a["href"].split("?")[0])

    if "flipkart." in domain:
        # PDP anchors present on search & review pages
        a = soup.select_one('a[href^="/p/itm"], a[href*="/p/"][href*="pid="]')
        if a and a.get("href"):
            return urljoin(base_url, a["href"].split("?")[0])

    if "reliancedigital." in domain or "croma." in domain:
        a = soup.select_one('a[href^="/p/"]')
        if a and a.get("href"):
            return urljoin(base_url, a["href"].split("?")[0])

    if "vijaysales." in domain:
        a = soup.select_one('a[href*="/product/"]')
        if a and a.get("href"):
            return urljoin(base_url, a["href"].split("?")[0])

    # Generic fallback
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if "/p/" in href or "/product/" in href or "/dp/" in href:
            return urljoin(base_url, href.split("?")[0])

    return None
