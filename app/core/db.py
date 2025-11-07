# app/core/db.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


# ✅ Create SQLAlchemy engine for Neon PostgreSQL
# Neon requires sslmode=require
engine = create_engine(
    settings.NEON_DB_URL,
    pool_pre_ping=True,   # auto-detect stale connections
    future=True,          # SQLAlchemy 2.0 style
)


# ✅ Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


# ✅ Dependency for FastAPI routes
def get_db():
    """
    Provides a scoped DB session. 
    Ensures proper cleanup on every request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
