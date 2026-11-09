"""Pytest fixtures providing an isolated in-memory async SQLite database seeded with test data."""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session
from app.main import app
from app.scripts.seed import seed_database

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        await seed_database(
            session,
            num_customers=120,
            num_leads=300,
            num_activities=400,
            reset=False,
        )

        async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_db_session] = _override_get_db
        yield session
        app.dependency_overrides.clear()

    await engine.dispose()
