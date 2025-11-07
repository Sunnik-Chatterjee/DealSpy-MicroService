# app/services/update.py

from sqlalchemy.orm import Session
from datetime import datetime
from app.models.product import Product
from app.services.tavily_search import resolve_product_url
from app.services.fetch_http import fetch_html
from app.services.extract_mistral import extract_from_html

def update_single_product(db: Session, pid: int):
    product = db.query(Product).filter(Product.pid == pid).first()
    if not product:
        return {"pid": pid, "status": "not_found"}

    # 1) Find PDP URL
    query = product.name
    url = resolve_product_url(query)

    if not url:
        return {"pid": pid, "status": "no_url"}

    # 2) Fetch HTML
    code, html = fetch_html(url)
    if code != 200:
        return {"pid": pid, "status": f"http_{code}", "url": url}

    # 3) Extract price + deep link
    extracted = extract_from_html(html, url)
    price = extracted.get("price_value")
    deep_link = extracted.get("deep_link") or url

    if price is None:
        return {"pid": pid, "status": "no_price", "url": url}

    # 4) Update fields
    product.deepLink = deep_link
    product.currentPrice = float(price)

    # update lowest price logic
    if product.lastLowestPrice is None or price < product.lastLowestPrice:
        product.lastLowestPrice = price
        product.isPriceDropped = True
    else:
        product.isPriceDropped = False

    db.add(product)
    db.commit()
    db.refresh(product)

    return {
        "pid": pid,
        "status": "ok",
        "currentPrice": price,
        "deepLink": deep_link
    }
