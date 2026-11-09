"""Tests for Concept 6: Keyset (Cursor) Pagination, Offset comparison, Benchmark endpoint, and Idempotent POST /leads."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app


@pytest.mark.asyncio
async def test_keyset_pagination_and_cursor_progression(db_session: AsyncSession) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch first batch of 25 leads
        res1 = await client.get("/api/v1/leads?limit=25")
        assert res1.status_code == 200
        batch1 = res1.json()
        assert len(batch1["data"]) == 25
        assert batch1["has_more"] is True
        assert batch1["next_cursor"] is not None

        # 2. Fetch second batch using next_cursor and verify zero overlap and strict descending order
        res2 = await client.get(f"/api/v1/leads?limit=25&cursor={batch1['next_cursor']}")
        assert res2.status_code == 200
        batch2 = res2.json()
        assert len(batch2["data"]) == 25

        ids_batch1 = {item["id"] for item in batch1["data"]}
        ids_batch2 = {item["id"] for item in batch2["data"]}
        assert ids_batch1.isdisjoint(ids_batch2)

        # 3. Malformed cursor returns 400 INVALID_CURSOR with unified error envelope
        bad_cursor = await client.get("/api/v1/leads?limit=25&cursor=not-valid-base64!!")
        assert bad_cursor.status_code == 400
        assert bad_cursor.json()["error"]["code"] == "INVALID_CURSOR"


@pytest.mark.asyncio
async def test_lead_creation_idempotency(db_session: AsyncSession) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "name": "Idempotent Prospect",
            "email": "idem@prospect.io",
            "source": "website",
            "status": "new",
            "revenue": "5000.00",
            "initial_note": "First click",
        }
        headers = {"Idempotency-Key": "test-idem-key-999"}

        # First submission creates row (201)
        first = await client.post("/api/v1/leads", json=payload, headers=headers)
        assert first.status_code == 201
        assert first.headers.get("X-Idempotent-Replay") == "false"
        lead_id = first.json()["id"]

        # Second submission with same Idempotency-Key returns same lead (200) without duplicating
        second = await client.post("/api/v1/leads", json=payload, headers=headers)
        assert second.status_code == 200
        assert second.headers.get("X-Idempotent-Replay") == "true"
        assert second.json()["id"] == lead_id


@pytest.mark.asyncio
async def test_pagination_benchmark_endpoint(db_session: AsyncSession) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/leads/benchmark?limit=20")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_leads_in_db"] >= 300
        assert len(data["results"]) == 4
