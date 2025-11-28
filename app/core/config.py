# app/core/config.py
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    tavily_api_key: str = Field(..., env="TAVILY_API_KEY")
    india_ecom_domains: str = Field(
        "amazon.in,flipkart.com",
        env="INDIA_ECOM_DOMAINS",
    )
    database_url: str = Field(..., env="DATABASE_URL")

    # 👇 This line is the important part
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # ignore extra env vars like mistral_api_key, user_agent
    )

    @property
    def india_domains_list(self) -> List[str]:
        return [
            d.strip()
            for d in self.india_ecom_domains.split(",")
            if d.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_india_domains() -> List[str]:
    return get_settings().india_domains_list
