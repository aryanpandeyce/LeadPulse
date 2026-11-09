"""Async SQLAlchemy 2.0 database engine and session management.

# CONCEPT: async/await in FastAPI (async SQLAlchemy + asyncpg connection pooling)
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy 2.0 ORM models."""


def _build_engine() -> AsyncEngine:
    is_sqlite = settings.database_url.startswith("sqlite")
    if is_sqlite:
        return create_async_engine(settings.database_url, echo=settings.debug)
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )


engine: AsyncEngine = _build_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session per request."""
    async with AsyncSessionLocal() as session:
        yield session

