from typing import List
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.search import search_products_sorted

router = APIRouter(prefix="/v1/search", tags=["search"])


class ProductData(BaseModel):
    productName: str
    price: float
    platform: str
    deepLink: str
    imageUrl: str | None = None


class SearchResponse(BaseModel):
    success: bool
    message: str
    data: List[ProductData]


@router.get("/", response_model=SearchResponse)
async def simple_product_search(
    q: str = Query(..., description="Product to search (e.g., 'iPhone 14 128GB')")
):

    return search_products_sorted(query=q, limit=25)
