# app/services/extract_mistral.py
import json
from bs4 import BeautifulSoup

def _jsonld_offers_price(soup: BeautifulSoup):
    out = {}
    for tag in soup.find_all("script", type="application/ld+json"):
        txt = (tag.string or tag.text or "").strip()
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            typ = node.get("@type", "")
            if typ and isinstance(typ, list):
                typ = " ".join(typ)
            if any(t in str(typ).lower() for t in ["product", "mobilephone", "thing"]):
                name = node.get("name")
                if name:
                    out["product_name"] = name
                offers = node.get("offers")
                if isinstance(offers, dict):
                    p = offers.get("price") or offers.get("priceSpecification", {}).get("price")
                    if p:
                        out["price_value"] = p
                elif isinstance(offers, list):
                    vals = []
                    for o in offers:
                        if isinstance(o, dict):
                            p = o.get("price") or (o.get("priceSpecification") or {}).get("price")
                            if p:
                                vals.append(p)
                    if vals:
                        out["price_value"] = min(vals)
    return out

def _meta_urls_name_category(soup: BeautifulSoup):
    out = {}
    og = soup.find("meta", property="og:url")
    if og and og.get("content"):
        out["og_url"] = og["content"]
    can = soup.find("link", rel=lambda v: v and "canonical" in v)
    if can and can.get("href"):
        out["canonical_url"] = can["href"]
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        out["product_name"] = og_title["content"]
    # breadcrumbs/category text (very rough)
    crumbs = soup.select("nav.breadcrumb, ul.breadcrumb, .breadcrumb")
    if crumbs:
        out["breadcrumbs"] = " > ".join(c.get_text(" ", strip=True) for c in crumbs)
    return out

def _fallback_visible_price(soup: BeautifulSoup):
    selectors = [
        "[id*=priceblock_dealprice]",
        "[id*=priceblock_ourprice]",
        "[id*=corePrice_feature_div]",
        "[class*=price] [class*=final]",
        "[class*=our-price]",
        "[class*=offer-price]",
        "[data-testid*=price]",
        "[data-test*=price]",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            txt = el.get_text(" ", strip=True)
            if txt:
                return {"price_value": txt}
    return {}

def extract_from_html(html: str, url: str):
    soup = BeautifulSoup(html or "", "html.parser")
    out = {"deep_link": url}

    out.update(_meta_urls_name_category(soup))

    jd = _jsonld_offers_price(soup)
    for k, v in jd.items():
        out.setdefault(k, v)

    if "price_value" not in out or out["price_value"] in (None, ""):
        out.update(_fallback_visible_price(soup))

    if "product_name" not in out or not out["product_name"]:
        if soup.title and soup.title.string:
            out["product_name"] = soup.title.string.strip()

    return out
