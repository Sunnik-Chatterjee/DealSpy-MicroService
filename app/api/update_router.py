# app/api/update_router.py
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.update import refresh_all_products_lowest_prices

router = APIRouter(prefix="/v1/update", tags=["update"])


class FailedItem(BaseModel):
    pid: int
    name: str
    reason: str


class RefreshAllResponse(BaseModel):
    success: bool
    total_products: int
    updated_count: int
    failed: List[FailedItem]


@router.post("/prices", response_model=RefreshAllResponse)
async def update_all_products_lowest_prices(
    db: Session = Depends(get_db),
):
    result = refresh_all_products_lowest_prices(db)

    return RefreshAllResponse(
        success=result.get("success", False),
        total_products=result.get("total_products", 0),
        updated_count=result.get("updated_count", 0),
        failed=[FailedItem(**item) for item in result.get("failed", [])],
    )
