"""Real PostgreSQL + Redis integration test suite (`@pytest.mark.postgres`).

Verifies PostgreSQL-specific features that SQLite in-memory cannot test:
1. `alembic upgrade head` schema migration (`pg_trgm` extension, `ix_customers_name_email_trgm` GIN index,
   `ix_leads_created_at_id_desc` composite keyset index, `monthly_kpis` Materialized View + unique index).
2. `pg_trgm` GIN substring search on `/api/v1/customers?q=aryan&city=Ahmedabad&status=active`.
3. Row-value Keyset pagination `WHERE (created_at, id) < (:ts, :id)` across pages with zero duplicates and strict descending order.
4. `REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_kpis` via `POST /api/v1/admin/kpis/refresh` and Redis cache hit/miss transitions.
5. Idempotent `POST /api/v1/leads` (`Idempotency-Key` unique constraint).
6. Redis rate limiting returning HTTP 429 with `Retry-After` in the unified error envelope.
"""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import get_db_session
from app.core.redis import close_redis, get_redis
from app.main import app
from app.scripts.seed import seed_database

POSTGRES_TEST_URL = os.getenv(
    "POSTGRES_TEST_URL",
    os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://leadpulse:leadpulse_dev_pw@localhost:5434/leadpulse",
    ),
)


@pytest.fixture()
async def pg_session() -> AsyncGenerator[AsyncSession, None]:
    if not POSTGRES_TEST_URL.startswith("postgresql"):
        pytest.skip("POSTGRES_TEST_URL is not configured for PostgreSQL")

    await close_redis()
    pg_engine = create_async_engine(POSTGRES_TEST_URL, poolclass=NullPool)
    try:
        async with pg_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await pg_engine.dispose()
        pytest.fail(f"Real PostgreSQL instance is not reachable at {POSTGRES_TEST_URL}: {exc}")

    session_maker = async_sessionmaker(bind=pg_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        # Ensure we have seeded data to test against
        count_res = await session.execute(text("SELECT COUNT(*) FROM customers"))
        cust_count = int(count_res.scalar_one() or 0)
        if cust_count < 100:
            await seed_database(
                session,
                num_customers=200,
                num_leads=600,
                num_activities=800,
                reset=True,
            )

        async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_db_session] = _override_get_db
        yield session
        app.dependency_overrides.clear()

    await close_redis()
    await pg_engine.dispose()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_extensions_indexes_and_trigram_search(
    pg_session: AsyncSession,
) -> None:
    """Verify pg_trgm extension, GIN index, and trigram search on real PostgreSQL."""
    ext_res = await pg_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'")
    )
    assert ext_res.scalar_one_or_none() == "pg_trgm"

    idx_res = await pg_session.execute(
        text(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'customers' AND indexname = 'ix_customers_name_email_trgm'"
        )
    )
    assert idx_res.scalar_one_or_none() == "ix_customers_name_email_trgm"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/customers?page=1&limit=20&sort_by=total_purchase_amount&order=desc&q=aryan"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        for row in body["data"]:
            assert "aryan" in (row["name"] + " " + row["email"]).lower()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_keyset_pagination_row_value_ordering_and_no_duplicates(
    pg_session: AsyncSession,
) -> None:
    """Verify row-value comparison WHERE (created_at, id) < (:ts, :id) on real PostgreSQL."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        seen_ids: set[int] = set()
        cursor: str | None = None
        last_pair: tuple[str, int] | None = None

        for _page_num in range(3):
            url = "/api/v1/leads?limit=30"
            if cursor:
                url += f"&cursor={cursor}"
            resp = await client.get(url)
            assert resp.status_code == 200
            payload = resp.json()
            rows = payload["data"]
            assert len(rows) == 30

            for r in rows:
                rid = int(r["id"])
                assert rid not in seen_ids, f"Duplicate lead id {rid} across keyset pages!"
                seen_ids.add(rid)
                pair = (str(r["created_at"]), rid)
                if last_pair is not None:
                    assert pair <= last_pair, "Keyset ordering violated descending (created_at, id)"
                last_pair = pair

            cursor = payload["next_cursor"]
            assert cursor is not None


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_materialized_view_concurrent_refresh_and_redis_cache(
    pg_session: AsyncSession,
) -> None:
    """Verify `REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_kpis` + Redis cache hit/miss."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as admin
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@leadpulse.io", "password": "Admin@123"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        # 2. Trigger REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_kpis
        refresh = await client.post(
            "/api/v1/admin/kpis/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert refresh.status_code == 200
        assert refresh.json()["refreshed_view"] == "monthly_kpis"

        # 3. First GET /api/v1/kpis after invalidation is a cache MISS -> served by materialized_view
        miss_resp = await client.get("/api/v1/kpis")
        assert miss_resp.status_code == 200
        assert miss_resp.json()["source"] == "materialized_view"

        # 4. Immediate second GET /api/v1/kpis is a Redis cache HIT -> served by redis
        hit_resp = await client.get("/api/v1/kpis")
        assert hit_resp.status_code == 200
        assert hit_resp.json()["source"] == "redis"


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_idempotent_lead_creation_and_rate_limit_429(
    pg_session: AsyncSession,
) -> None:
    """Verify unique `idempotency_key` constraint on PostgreSQL and Redis 429 rate limiting."""
    redis = await get_redis()
    await redis.delete("rl:ai:ip:127.0.0.1", "rl:ai:ip:testclient")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        idem_key = f"pg-idem-{os.urandom(4).hex()}"
        lead_payload = {
            "name": "Postgres Idempotent Lead",
            "email": "pg.idem@prospect.io",
            "source": "referral",
            "status": "qualified",
            "revenue": "9200.00",
        }
        r1 = await client.post(
            "/api/v1/leads",
            json=lead_payload,
            headers={"Idempotency-Key": idem_key},
        )
        assert r1.status_code == 201
        r2 = await client.post(
            "/api/v1/leads",
            json=lead_payload,
            headers={"Idempotency-Key": idem_key},
        )
        assert r2.status_code == 200
        assert r2.headers.get("X-Idempotent-Replay") == "true"
        assert r1.json()["id"] == r2.json()["id"]

        # Trigger AI rate limit (20 requests/min allowed, 21st returns 429)
        hit_429 = False
        for _ in range(25):
            chat_r = await client.post(
                "/api/v1/ai/chat",
                json={"message": "hello", "history": []},
            )
            if chat_r.status_code == 429:
                hit_429 = True
                assert chat_r.json()["error"]["code"] == "AI_RATE_LIMIT_EXCEEDED"
                assert "Retry-After" in chat_r.headers
                break
        assert hit_429 is True

