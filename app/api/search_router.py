# app/api/search_router.py
from typing import List, Optional
from fastapi import APIRouter, Query
from app.services.preview_search import preview_lowest_by_name

router = APIRouter(prefix="/v1/search", tags=["preview"])

@router.get("/lowest")
def lowest_by_name(
    q: str = Query(..., description="Product name to search"),
    domains: Optional[List[str]] = Query(None, description="Override India domains"),
):
    """
    Read-only search: returns lowest price + deeplink across India sites for the given product name.
    Does not write to DB.
    """
    return preview_lowest_by_name(q, domains)
