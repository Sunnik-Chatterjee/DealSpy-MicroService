# app/models/product.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Boolean, Integer, Text

class Base(DeclarativeBase):
    pass

class Product(Base):
    __tablename__ = "product"

    pid: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # map attributes -> existing snake_case columns in DB
    currentPrice: Mapped[float | None] = mapped_column("current_price", Float, nullable=True)
    lastLowestPrice: Mapped[float | None] = mapped_column("last_lowest_price", Float, nullable=True)
    isPriceDropped: Mapped[bool | None] = mapped_column("is_price_dropped", Boolean, nullable=True)

    imageUrl: Mapped[str | None] = mapped_column("image_url", String(1024), nullable=True)
    # if your column is literally named `desc`, keep it; else change to the real name (e.g., "description")
    desc: Mapped[str | None] = mapped_column("desc", Text, nullable=True)

    deepLink: Mapped[str | None] = mapped_column("deep_link", String(1024), nullable=True)
