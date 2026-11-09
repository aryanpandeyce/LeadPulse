"""Tests for Concept 4: Unified Error Envelope, Request-ID correlation, and Global Exception Handlers."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_sets_request_id() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "X-Request-ID" in resp.headers
        assert data["request_id"] == resp.headers["X-Request-ID"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,expected_status,expected_code",
    [
        ("validation", 400, "INVALID_PARAMETER"),
        ("unauthorized", 401, "TOKEN_EXPIRED"),
        ("forbidden", 403, "ADMIN_ROLE_REQUIRED"),
        ("not_found", 404, "LEAD_NOT_FOUND"),
        ("conflict", 409, "DUPLICATE_LEAD_SUBMISSION"),
        ("rate_limit", 429, "AI_RATE_LIMIT_EXCEEDED"),
        ("external", 502, "LLM_UPSTREAM_TIMEOUT"),
        ("unhandled", 500, "INTERNAL_SERVER_ERROR"),
    ],
)
async def test_error_envelope_across_all_status_codes(
    kind: str, expected_status: int, expected_code: str
) -> None:
    """Verify every error class returns the exact canonical error envelope and never leaks secrets."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        custom_req_id = f"req-test-{kind}"
        resp = await client.get(
            f"/api/v1/error-demo?kind={kind}",
            headers={"X-Request-ID": custom_req_id},
        )
        assert resp.status_code == expected_status
        assert resp.headers.get("X-Request-ID") == custom_req_id

        body = resp.json()
        assert "error" in body
        err = body["error"]
        assert err["code"] == expected_code
        assert err["status"] == expected_status
        assert err["request_id"] == custom_req_id
        assert isinstance(err["details"], list)

        # Ensure unhandled 500 never leaks stack traces or sensitive strings
        if expected_status == 500:
            assert "secret_token" not in resp.text
            assert "RuntimeError" not in resp.text

        # Ensure 429 includes Retry-After header
        if expected_status == 429:
            assert resp.headers.get("Retry-After") == "45"

