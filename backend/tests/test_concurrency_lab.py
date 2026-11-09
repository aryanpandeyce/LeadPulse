"""Tests for Concept 3: FastAPI Concurrency Lab endpoints and ProcessPool CPU job polling."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_concurrency_lab_endpoints() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. /lab/io-async
        r_async = await client.get("/api/v1/lab/io-async?delay_ms=10")
        assert r_async.status_code == 200
        assert r_async.json()["mode"] == "io_async_gather"

        # 2. /lab/io-blocking-wrong
        r_wrong = await client.get("/api/v1/lab/io-blocking-wrong?delay_ms=10")
        assert r_wrong.status_code == 200
        assert r_wrong.json()["mode"] == "io_blocking_wrong"

        # 3. /lab/io-blocking-right
        r_right = await client.get("/api/v1/lab/io-blocking-right?delay_ms=10")
        assert r_right.status_code == 200
        assert r_right.json()["mode"] == "io_blocking_right"

        # 4. /lab/cpu-heavy background job + polling /lab/jobs/{id}
        job_resp = await client.post(
            "/api/v1/lab/cpu-heavy", json={"rows_to_process": 5000}
        )
        assert job_resp.status_code == 202
        job_id = job_resp.json()["job_id"]

        # Poll until completed
        status = "queued"
        for _ in range(20):
            await asyncio.sleep(0.05)
            poll = await client.get(f"/api/v1/lab/jobs/{job_id}")
            assert poll.status_code == 200
            status = poll.json()["status"]
            if status == "completed":
                assert poll.json()["checksum"] is not None
                break
        assert status == "completed"
