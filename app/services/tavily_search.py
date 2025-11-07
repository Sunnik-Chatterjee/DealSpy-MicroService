import httpx
from typing import Dict, Optional, List
from app.core.config import settings, get_india_domains

TAVILY_URL = "https://api.tavily.com/search"

def resolve_url_for_domain(query: str, domain: str) -> Optional[str]:
    payload = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "include_domains": [domain],
        "max_results": 5,
        "search_depth": "basic",
    }
    r = httpx.post(TAVILY_URL, json=payload, timeout=20.0)
    r.raise_for_status()
    data = r.json()
    for item in data.get("results", []):
        url = item.get("url")
        if url and domain in url:
            return url
    return None

def resolve_urls_all_sites(query: str, domains: Optional[List[str]] = None) -> Dict[str, Optional[str]]:
    domains = domains or get_india_domains()
    results: Dict[str, Optional[str]] = {}
    for d in domains:
        results[d] = resolve_url_for_domain(query, d)
    return results
