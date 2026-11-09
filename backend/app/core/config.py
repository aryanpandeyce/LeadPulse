"""Application configuration managed via Pydantic Settings (.env)."""

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_JWT_SECRET = "change-me-in-production-to-a-secure-32-byte-secret-key"


def normalize_asyncpg_url(url: str) -> str:
    """Convert cloud `postgres://` or `postgresql://` URLs to `postgresql+asyncpg://`
    and translate libpq query params (`sslmode=require`) for `asyncpg`.
    """
    raw = url.strip()
    if raw.startswith("postgres://"):
        raw = "postgresql+asyncpg://" + raw[len("postgres://") :]
    elif raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://") :]
    elif raw.startswith("postgresql+psycopg2://") or raw.startswith("postgresql+psycopg://"):
        raw = "postgresql+asyncpg://" + raw.split("://", 1)[1]

    if raw.startswith("postgresql+asyncpg://") and "?" in raw:
        parts = urlsplit(raw)
        query_items = dict(parse_qsl(parts.query, keep_blank_values=True))
        if "sslmode" in query_items:
            sslmode = query_items.pop("sslmode")
            if sslmode in ("require", "verify-ca", "verify-full") and "ssl" not in query_items:
                query_items["ssl"] = "require"
        query_items.pop("channel_binding", None)
        raw = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment)
        )
    return raw


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
    database_url: str = "postgresql+asyncpg://leadpulse:leadpulse_dev_pw@localhost:5434/leadpulse"
    direct_database_url: str = ""
    db_pool_size: int = 10
    db_max_overflow: int = 20
    process_pool_max_workers: int = 2

    # Seed Configuration
    seed_size: Literal["small", "full"] = "full"
    seed_admin_password: str = "Admin@123"
    seed_agent_password: str = "Agent@123"

    # Redis (supports both redis:// and TLS rediss://)
    redis_url: str = "redis://localhost:6380/0"
    kpi_cache_ttl_seconds: int = 300
    llm_cache_ttl_seconds: int = 3600

    # Security & JWT
    jwt_secret_key: str = DEFAULT_DEV_JWT_SECRET
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

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        return normalize_asyncpg_url(v)

    @field_validator("direct_database_url", mode="before")
    @classmethod
    def validate_direct_database_url(cls, v: str) -> str:
        if not v:
            return ""
        return normalize_asyncpg_url(v)

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

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment == "production":
            self.debug = False
            if self.jwt_secret_key == DEFAULT_DEV_JWT_SECRET or len(self.jwt_secret_key) < 24:
                raise ValueError(
                    "In production, JWT_SECRET_KEY must be set to a strong secret (>=24 chars) and not the default."
                )
            if "*" in self.cors_origins:
                raise ValueError(
                    "In production, CORS_ORIGINS must be an explicit list and cannot contain wildcard '*'."
                )
        return self

    @property
    def is_demo_ai_mode(self) -> bool:
        """True when running with deterministic mock provider or without live LLM API keys."""
        if self.llm_provider == "mock":
            return True
        if self.llm_provider == "openai" and not self.openai_api_key:
            return True
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            return True
        return False

    @property
    def sanitized_db_host(self) -> str:
        parts = urlsplit(self.database_url)
        return parts.hostname or "sqlite"

    @property
    def sanitized_redis_host(self) -> str:
        parts = urlsplit(self.redis_url)
        return parts.hostname or "localhost"


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton instance of Settings."""
    return Settings()
