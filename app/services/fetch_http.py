# app/services/fetch_http.py

from typing import Dict, Any, Tuple, Optional
from app.core.http import get_client


def fetch_http(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Tuple[int, str, str]:
    """
    Generic HTTP fetch using the shared httpx client.
    Returns: (status_code, text_body_if_200_else_empty, final_url)
    """
    client = get_client()

    # Merge per-call headers ON TOP of default headers
    if headers:
        client.headers.update(headers)

    if method.upper() == "POST":
        resp = client.post(url, json=json, data=data)
    else:
        resp = client.get(url, params=data)

    if resp.status_code == 200:
        return resp.status_code, resp.text, str(resp.url)
    return resp.status_code, "", str(resp.url)


def fetch_html(url: str) -> Tuple[int, str]:
    """
    Convenience wrapper for simple GET of an HTML page.
    Returns: (status_code, text_body_if_200_else_empty)
    """
    status, text, _ = fetch_http(url, method="GET")
    return status, text
