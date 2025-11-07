# app/services/domain_registry.py

DOMAIN_CAPS = {
    "amazon.in": {
        "pdp_patterns": ["/dp/", "/gp/product/"],
        "supports_search_fallback": True,
    },
    "flipkart.com": {
        "pdp_patterns": ["/p/itm"],
        "supports_search_fallback": True,
    },
    "reliancedigital.in": {
        "pdp_patterns": ["/p/"],
        "supports_search_fallback": True,
    },
    "croma.com": {
        "pdp_patterns": ["/p/"],
        "supports_search_fallback": True,
    },
    "vijaysales.com": {
        "pdp_patterns": ["/product/"],
        "supports_search_fallback": True,
    },

    # You can add new domains here later:
    # "tatacliq.com": {...}
    # "meesho.com": {...}
    # "ajio.com": {...}
}

def has_capabilities(domain: str) -> bool:
    domain = domain.lower()
    for key in DOMAIN_CAPS.keys():
        if domain.endswith(key):
            return True
    return False

def get_caps(domain: str):
    domain = domain.lower()
    for key, caps in DOMAIN_CAPS.items():
        if domain.endswith(key):
            return caps
    return None
