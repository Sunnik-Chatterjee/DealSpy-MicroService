# app/services/product_guards.py
import re
from typing import Optional, Tuple

# Compiled, case-insensitive
ACCESSORY_NEGATIVE = [
    re.compile(r"\bcase(s)?\b", re.I),
    re.compile(r"\bcover(s)?\b", re.I),
    re.compile(r"\bsilicone\b", re.I),
    re.compile(r"\bbumper\b", re.I),
    re.compile(r"\bback\s*cover\b", re.I),
    re.compile(r"\btempered\b", re.I),
    re.compile(r"\bscreen\s*protector\b", re.I),
    re.compile(r"\bglass\b", re.I),
    re.compile(r"\bcharger(s)?\b", re.I),
    re.compile(r"\bpower\s*bank(s)?\b", re.I),
    re.compile(r"\bcable(s)?\b", re.I),
    re.compile(r"\badapter(s)?\b", re.I),
    re.compile(r"\bearbuds?\b", re.I),
    re.compile(r"\bheadphones?\b", re.I),
    re.compile(r"\bneckband\b", re.I),
    re.compile(r"\bstrap(s)?\b", re.I),
    re.compile(r"\bstand(s)?\b", re.I),
    re.compile(r"\bcar\s*mount\b", re.I),
    re.compile(r"\bmagsafe\b", re.I),
    re.compile(r"\bwallet\b", re.I),
]

NEGATIVE_VARIANTS = [
    re.compile(r"\bpro\s*max\b", re.I),
    re.compile(r"\bpro\b", re.I),
    re.compile(r"\bplus\b", re.I),
    re.compile(r"\bmax\b", re.I),
]

POSITIVE_IPHONE15 = [
    re.compile(r"\biphone\s*15\b", re.I),
]

RENEWED_WORDS = [
    re.compile(r"\brenewed\b", re.I),
    re.compile(r"\brefurb(ished|)\b", re.I),
    re.compile(r"\bpre[-\s]*owned\b", re.I),
]

def looks_like_accessory(text: Optional[str]) -> bool:
    t = text or ""
    return any(rx.search(t) for rx in ACCESSORY_NEGATIVE)

def query_targets_iphone15(query: str) -> bool:
    q = query or ""
    return any(rx.search(q) for rx in POSITIVE_IPHONE15)

def is_correct_variant(product_name: str, query: str) -> bool:
    """
    Requires 'iPhone 15' in product_name.
    If query didn't ask for Pro/Plus/Max, reject those variants.
    """
    name = product_name or ""
    if not any(rx.search(name) for rx in POSITIVE_IPHONE15):
        return False

    asked_variant = any(rx.search(query or "") for rx in NEGATIVE_VARIANTS)
    if not asked_variant:
        if any(rx.search(name) for rx in NEGATIVE_VARIANTS):
            return False
    return True

def is_phone_category(category_text: Optional[str]) -> bool:
    """
    Accepts Mobile, Mobiles, Smartphone, Mobile Phone, Cell Phone.
    """
    t = (category_text or "").lower()
    return any(k in t for k in ["mobile", "smartphone", "cell phone", "mobile phone"])

def validate_query(query: str) -> Tuple[bool, str]:
    """
    Early guard so accessory-only or off-topic queries don't crash the flow.
    Returns (ok, reason).
    """
    if looks_like_accessory(query):
        return False, "query_is_accessory"
    if not query_targets_iphone15(query):
        return False, "query_missing_model_keyword"
    return True, ""

def is_renewed(text: Optional[str]) -> bool:
    t = text or ""
    return any(rx.search(t) for rx in RENEWED_WORDS)

def query_allows_renewed(query: str) -> bool:
    return is_renewed(query)