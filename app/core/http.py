# app/core/http.py

import httpx
from app.core.config import settings


def get_client() -> httpx.Client:
    """
    Returns a configured HTTP client for all scraping & fetching.
    You can reuse this client inside services.
    """
    return httpx.Client(
        headers={
            "User-Agent": settings.USER_AGENT,
            "Accept-Language": "en-IN,en;q=0.9",
        },
        timeout=25.0,
        follow_redirects=True,
        verify=True,  # SSL verification ON
    )
