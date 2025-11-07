# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    NEON_DB_URL: str
    MISTRAL_API_KEY: str
    TAVILY_API_KEY: str

    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

    # You can fully override this in .env
    INDIA_ECOM_DOMAINS: str = (
        "amazon.in,flipkart.com,reliancedigital.in,croma.com,"
        "vijaysales.com"
    )

    MISTRAL_MODEL: str = "mistral-small-latest"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()


def get_india_domains() -> List[str]:
    raw = settings.INDIA_ECOM_DOMAINS
    if not raw:
        return []
    return [
        d.strip().lower()
        for d in raw.split(",")
        if d.strip()
    ]
