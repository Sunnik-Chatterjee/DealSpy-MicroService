# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router

app = FastAPI(title="Price Updater Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"service": "price-updater", "status": "ok"}

@app.get("/healthz")
def healthz():
    return {"ok": True}

app.include_router(api_router)  # <-- this line is critical
