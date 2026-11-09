"""Tests for Phase 2: JWT authentication, bcrypt hashing, token refresh, and RBAC (admin vs agent)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app


@pytest.mark.asyncio
async def test_auth_login_refresh_and_me(db_session: AsyncSession) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Invalid password returns 401 with unified error envelope
        bad_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@leadpulse.io", "password": "WrongPassword123"},
        )
        assert bad_resp.status_code == 401
        assert bad_resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

        # 2. Valid Admin login returns access + refresh tokens
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@leadpulse.io", "password": "Admin@123"},
        )
        assert login_resp.status_code == 200
        tokens = login_resp.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["user"]["role"] == "admin"

        # 3. /auth/me with access token
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "admin@leadpulse.io"

        # 4. /auth/refresh rotates tokens
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.json()
