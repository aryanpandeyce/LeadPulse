"""Tests for Concept 2: Server-side paginated, sortable, filterable customers table + column whitelisting."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app


@pytest.mark.asyncio
async def test_customers_pagination_sorting_filtering_and_search(
    db_session: AsyncSession,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Standard filtered + sorted + searched request matching prompt spec:
        # GET /api/v1/customers?page=1&limit=50&sort_by=name&order=asc&city=Ahmedabad&status=active&q=aryan
        resp = await client.get(
            "/api/v1/customers?page=1&limit=50&sort_by=name&order=asc&city=Ahmedabad&status=active&q=aryan"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "total" in body
        assert body["page"] == 1
        assert body["limit"] == 50
        assert "total_pages" in body

        # 2. Disallowed sort_by column is rejected with 400 INVALID_SORT_COLUMN (prevents SQL injection)
        bad_sort = await client.get(
            "/api/v1/customers?page=1&limit=50&sort_by=hashed_password;DROP TABLE users--"
        )
        assert bad_sort.status_code == 400
        assert bad_sort.json()["error"]["code"] == "INVALID_SORT_COLUMN"

        # 3. Limit > 100 is rejected with 400 MAX_LIMIT_EXCEEDED
        bad_limit = await client.get("/api/v1/customers?page=1&limit=500")
        assert bad_limit.status_code == 400
        assert bad_limit.json()["error"]["code"] == "MAX_LIMIT_EXCEEDED"

        # 4. Streamed CSV export works
        csv_resp = await client.get("/api/v1/customers/export.csv?city=Ahmedabad&status=active")
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers.get("content-type", "")
        lines = csv_resp.text.strip().splitlines()
        assert lines[0].startswith("id,name,email,phone,city,status")
        assert len(lines) >= 2

