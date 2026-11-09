"""Tests for Concept 5: Two-layer KPI caching (Redis + Materialized View + Raw slow path + Admin refresh RBAC)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app


@pytest.mark.asyncio
async def test_kpi_caching_layers_and_admin_refresh(db_session: AsyncSession) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. First call to /api/v1/kpis?bypass_redis=true hits materialized_view
        mv_resp = await client.get("/api/v1/kpis?bypass_redis=true")
        assert mv_resp.status_code == 200
        mv_data = mv_resp.json()
        assert mv_data["source"] == "materialized_view"
        assert mv_data["total_leads"] >= 300

        # 2. Second call to /api/v1/kpis (default) hits Redis cache-aside
        redis_resp = await client.get("/api/v1/kpis")
        assert redis_resp.status_code == 200
        redis_data = redis_resp.json()
        assert redis_data["source"] == "redis"
        assert redis_data["total_leads"] == mv_data["total_leads"]

        # 3. Slow path /api/v1/kpis/raw returns source="raw"
        raw_resp = await client.get("/api/v1/kpis/raw")
        assert raw_resp.status_code == 200
        assert raw_resp.json()["source"] == "raw"

        # 4. Agent user cannot call POST /api/v1/admin/kpis/refresh (403 FORBIDDEN)
        agent_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "agent@leadpulse.io", "password": "Agent@123"},
        )
        agent_token = agent_login.json()["access_token"]
        forbidden_resp = await client.post(
            "/api/v1/admin/kpis/refresh",
            headers={"Authorization": f"Bearer {agent_token}"},
        )
        assert forbidden_resp.status_code == 403
        assert forbidden_resp.json()["error"]["code"] == "ADMIN_ROLE_REQUIRED"

        # 5. Admin user can call POST /api/v1/admin/kpis/refresh and bumps cache version
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@leadpulse.io", "password": "Admin@123"},
        )
        admin_token = admin_login.json()["access_token"]
        refresh_resp = await client.post(
            "/api/v1/admin/kpis/refresh",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert refresh_resp.status_code == 200
        assert refresh_resp.json()["new_cache_version"] >= 2

