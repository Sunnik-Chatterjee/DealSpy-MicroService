# app/api/router.py
from fastapi import APIRouter
from app.api.update_router import router as update_router
from app.api.search_router import router as search_router 

api_router = APIRouter()
api_router.include_router(update_router)
api_router.include_router(search_router) 
