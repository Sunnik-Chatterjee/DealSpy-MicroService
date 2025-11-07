# app/services/price_utils.py
import re
from typing import Optional

PRICE_RX = re.compile(r'(?:₹|INR|Rs\.?)\s*([0-9][0-9,]*)(?:\.\d{1,2})?', re.I)

def parse_price_loose(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value)
    m = PRICE_RX.search(s)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except Exception:
            return None
    digits = re.sub(r"[^\d.]", "", s)
    try:
        return float(digits) if digits else None
    except Exception:
        return None

def min_expected_price_for_query(query: str) -> Optional[float]:
    """
    Return a floor only when we're confident (e.g., iPhone 15).
    Otherwise, return None (no floor).
    """
    q = (query or "").lower()
    if "iphone 15" in q:
        return 30000.0   # conservative floor for new iPhone 15
    return None         # <— no default floor

def parse_price_strict(value, min_floor: Optional[float]) -> Optional[float]:
    amt = parse_price_loose(value)
    if amt is None:
        return None
    if min_floor is not None and amt < min_floor:
        return None
    return amt
