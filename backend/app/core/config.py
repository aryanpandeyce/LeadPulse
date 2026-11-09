"""Application configuration managed via Pydantic Settings (.env)."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "LeadPulse API"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://leadpulse:leadpulse_dev_pw@localhost:5432/leadpulse"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    kpi_cache_ttl_seconds: int = 300
    llm_cache_ttl_seconds: int = 3600

    # Security & JWT
    jwt_secret_key: str = "change-me-in-production-to-a-secure-32-byte-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: list[str] = ["http://localhost:3000"]

    # LLM Provider Configuration
    # CONCEPT: Controlling LLM cost in production (configurable cheap + strong models)
    llm_provider: Literal["mock", "openai", "anthropic"] = "mock"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_cheap_model: str = "gpt-4o-mini"
    llm_strong_model: str = "gpt-4o"
    llm_daily_user_budget_usd: float = 1.00
    llm_rate_limit_per_minute: int = 20

    # CONCEPT: Feature flags (Balancing shipping speed vs code quality)
    feature_ai_streaming: bool = True
    feature_smart_capture_retry: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json

                parsed: list[str] = json.loads(v)
                return parsed
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton instance of Settings."""
    return Settings()

