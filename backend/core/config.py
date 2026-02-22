"""
Core configuration module using pydantic-settings.
Loads from environment variables and .env file.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "SEO Intelligence Platform"
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-in-production-min-32-chars!!"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [origin.strip() for origin in v.split(",")]
        return v

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://seouser:seopassword@localhost:5432/seodb"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    DATABASE_POOL_TIMEOUT: int = 30

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CELERY_URL: str = "redis://localhost:6379/1"
    REDIS_CACHE_URL: str = "redis://localhost:6379/2"
    REDIS_RATE_LIMIT_URL: str = "redis://localhost:6379/3"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_WORKER_CONCURRENCY: int = 8
    CELERY_MAX_TASKS_PER_CHILD: int = 1000

    # Crawler
    CRAWLER_MAX_CONCURRENT: int = 100
    CRAWLER_MAX_DEPTH: int = 10
    CRAWLER_REQUEST_TIMEOUT: int = 30
    CRAWLER_MAX_RETRIES: int = 3
    CRAWLER_RETRY_DELAY: int = 2
    CRAWLER_USER_AGENT: str = "SEOBot/1.0 (+https://yourdomain.com/bot)"
    CRAWLER_RATE_LIMIT_RPS: int = 10
    CRAWLER_JS_RENDER_TIMEOUT: int = 15000

    # Playwright
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_BROWSER: str = "chromium"

    # Scoring Weights
    SCORE_TECHNICAL_WEIGHT: float = 0.35
    SCORE_CONTENT_WEIGHT: float = 0.30
    SCORE_AUTHORITY_WEIGHT: float = 0.20
    SCORE_LINKING_WEIGHT: float = 0.10
    SCORE_AI_VISIBILITY_WEIGHT: float = 0.05

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()