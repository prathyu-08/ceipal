"""
config/settings.py
------------------
Centralised configuration loaded from .env file.
All secrets and base URLs are read once here and reused across the app.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # CEIPAL credentials
    ceipal_base_url: str = "https://api.ceipal.com"
    ceipal_web_base_url: str = "https://talenthirecls2.ceipal.com"
    ceipal_username: str = ""
    ceipal_password: str = ""
    ceipal_api_key: str = ""

    # App settings
    app_env: str = "development"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    redis_url: str = ""
    request_dedupe_ttl_seconds: int = 30
    high_priority_cache_ttl_seconds: int = 15 * 60
    status_cache_ttl_seconds: int = 2 * 60
    bdm_performance_cache_ttl_seconds: int = 5 * 60
    today_submissions_cache_ttl_seconds: int = 60
    submissions_cache_ttl_seconds: int = 60
    jobs_date_cache_ttl_seconds: int = 2 * 60
    jobposts_screen_cache_ttl_seconds: int = 5 * 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()
