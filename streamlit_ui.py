# streamlit_ui.py — Preview-only (search by name → lowest price + details)

import os
import json
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv
import httpx
import pandas as pd
import re

# Load .env
load_dotenv()

DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return "unknown"

st.set_page_config(page_title="DealSpy – Lowest Price Preview", page_icon="🛍️", layout="wide")
st.title("🛍️ DealSpy • Lowest Price (India) — Preview Only")

backend_url = st.text_input(
    "FastAPI backend URL",
    value=DEFAULT_BACKEND_URL,
    help="Your FastAPI base URL (e.g., http://localhost:8000)"
)

st.divider()

col_q, col_btn = st.columns([4, 1])
with col_q:
    query = st.text_input("Product name", placeholder="e.g., iPhone 15 128GB Black")
with col_btn:
    do_preview = st.button("Find Lowest Price", use_container_width=True)

if do_preview:
    if not query.strip():
        st.warning("Please enter a product name.")
        st.stop()

    preview_url = backend_url.rstrip("/") + "/v1/search/lowest"

    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(preview_url, params={"q": query})
            if resp.status_code != 200:
                st.error(f"Backend error ({resp.status_code}): {resp.text}")
                st.stop()
            data = resp.json()
    except Exception as e:
        st.error(f"Failed to reach backend: {e}")
        st.stop()

    with st.expander("Raw response (debug)"):
        st.code(json.dumps(data, indent=2))

    status = data.get("status")

    # Friendly messages for early validation / no-deal
    if status in ("query_is_accessory", "query_missing_model_keyword", "no_deal"):
        st.warning(data.get("message") or "No matching product/price found.")
        # Show why domains failed (handy during testing)
        details = data.get("details", [])
        if details:
            try:
                df = pd.DataFrame(details)
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception:
                st.code(json.dumps(details, indent=2))
        st.stop()

    if status != "ok":
        st.warning("No price found across India domains for this name.")
        details = data.get("details", [])
        if details:
            try:
                df = pd.DataFrame(details)
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception:
                st.code(json.dumps(details, indent=2))
        st.stop()

    # Success view
    pname       = data.get("product_name") or query
    best_price  = data.get("currentPrice")
    best_link   = (data.get("deepLink") or "").strip()
    best_domain = data.get("selected_domain") or extract_domain(best_link)

    st.subheader(pname)

    top = st.container(border=True)
    with top:
        c1, c2, c3 = st.columns([2, 2, 3])
        with c1:
            txt_price = f"₹ {best_price:,.2f}" if isinstance(best_price, (int, float)) else "—"
            st.metric("Lowest Price (today)", txt_price)
        with c2:
            st.write("**Website**")
            st.code(best_domain or "—")
        with c3:
            if best_link:
                st.link_button("Go to lowest price", best_link, use_container_width=True)
            else:
                st.info("No deeplink available")

    # Per-site details table (sorted nicely)
    details = data.get("details", [])
    if isinstance(details, list) and details:
        rows = []
        for d in details:
            rows.append({
                "domain": d.get("domain"),
                "status": d.get("status"),
                "price": d.get("price"),
                "name": d.get("name"),
                "url": d.get("url"),
            })
        df = pd.DataFrame(rows)

        # Status order: good first
        status_rank = {
            "ok": 0,
            "variant_mismatch": 1,
            "rejected_accessory": 2,
            "category_mismatch": 3,
            "not_pdp_url": 4,
            "no_price": 5,
            "no_valid_pdp": 6,
            "http_200": 7,
            "http_403": 8,
            "http_404": 9,
            "http_0": 10,
            "no_url": 11,
        }
        df["status_rank"] = df["status"].map(status_rank).fillna(99).astype(int)

        def to_num(x):
            if x is None:
                return float("nan")
            if isinstance(x, (int, float)):
                return float(x)
            s = re.sub(r"[^\d.]", "", str(x))
            try:
                return float(s) if s else float("nan")
            except Exception:
                return float("nan")

        df["price_num"] = df["price"].map(to_num)

        df_sorted = df.sort_values(
            by=["status_rank", "price_num"],
            na_position="last",
            kind="stable"
        )

        st.markdown("### Per-site details")
        st.dataframe(
            df_sorted[["domain", "status", "price", "name", "url"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No per-site details returned.")
