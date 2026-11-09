"""Observability and Error Envelope Demo endpoints (/health, /ready, /error-demo)."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.errors import (
    ConflictError,
    ExternalServiceError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)
from app.core.logging import get_request_id
from app.core.redis import get_redis

router = APIRouter(tags=["Observability & Health"])


@router.get("/health", summary="Liveness probe")
async def health_check() -> dict[str, str]:
    """Fast liveness check used by container orchestrators and load balancers."""
    return {
        "status": "ok",
        "service": "leadpulse-backend",
        "request_id": get_request_id(),
    }


@router.get("/ready", summary="Readiness probe checking PostgreSQL and Redis")
async def readiness_check(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Verify downstream dependencies (PostgreSQL and Redis) are reachable."""
    db_ok = False
    redis_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    try:
        redis = await get_redis()
        await redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "status": "ready" if (db_ok and redis_ok) else "degraded",
        "checks": {
            "database": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
        },
        "request_id": get_request_id(),
    }


@router.get(
    "/error-demo",
    summary="Trigger specific error codes to verify the Unified Error Envelope (Concept 4)",
)
async def trigger_error_demo(
    kind: str = Query(
        default="not_found",
        description="Error type to trigger: validation | unauthorized | forbidden | not_found | conflict | rate_limit | external | unhandled",
    ),
) -> dict[str, str]:
    """# CONCEPT: Error handling & good error design
    Allows the UI, automated tests, and interviewers to trigger any error class on demand
    and inspect the standardized error envelope + X-Request-ID correlation header.
    """
    if kind == "validation":
        raise ValidationError(
            code="INVALID_PARAMETER",
            message="Provided filter parameter is not allowed",
            details=[{"field": "kind", "issue": "Simulated domain validation failure"}],
        )
    if kind == "unauthorized":
        raise UnauthorizedError(
            code="TOKEN_EXPIRED",
            message="Your access token has expired. Please refresh your session.",
        )
    if kind == "forbidden":
        raise ForbiddenError(
            code="ADMIN_ROLE_REQUIRED",
            message="Only administrators can perform this operation.",
        )
    if kind == "not_found":
        raise NotFoundError(
            code="LEAD_NOT_FOUND",
            message="Lead with ID 'lead_999999' was not found",
        )
    if kind == "conflict":
        raise ConflictError(
            code="DUPLICATE_LEAD_SUBMISSION",
            message="A lead with this idempotency key or email was already submitted.",
        )
    if kind == "rate_limit":
        raise RateLimitError(
            code="AI_RATE_LIMIT_EXCEEDED",
            message="Rate limit of 20 AI requests per minute exceeded.",
            retry_after=45,
        )
    if kind == "external":
        raise ExternalServiceError(
            code="LLM_UPSTREAM_TIMEOUT",
            message="Upstream LLM provider failed after 2 retries.",
        )
    if kind == "unhandled":
        raise RuntimeError("Simulated unexpected internal database/runtime crash (secret_token=xyz)")

    return {"status": "no_error_triggered", "request_id": get_request_id()}

