# app/models/product.py

from sqlalchemy import Boolean, Column, Float, Integer, String
from app.core.db import Base


class Product(Base):
    __tablename__ = "product"

    pid = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String, unique=True, nullable=False)

    # map to existing DB columns
    current_price = Column("current_price", Float, nullable=True)
    last_lowest_price = Column("last_lowest_price", Float, nullable=True)
    is_price_dropped = Column("is_price_dropped", Boolean, nullable=True)
    image_url = Column("image_url", String, nullable=True)

    # desc column already exists as "desc"
    desc = Column("desc", String, nullable=True)

    deep_link = Column("deep_link", String, nullable=True)
