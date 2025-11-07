# app/api/update_router.py
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.db import get_db
from app.services.update_product import (
    update_single_product_lowest,
    update_products_lowest,
)

router = APIRouter(prefix="/v1/products", tags=["prices"])

@router.get("/update-lowest/{pid}")
def update_lowest(pid: int, db: Session = Depends(get_db)):
    return update_single_product_lowest(db, pid)

@router.post("/update-lowest-batch")
def update_lowest_batch(pids: List[int] = Body(..., embed=False), db: Session = Depends(get_db)):
    return update_products_lowest(db, pids)
