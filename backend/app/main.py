"""FastAPI application entrypoint."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ai, auth, customers, health, kpis, lab, leads
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.redis import close_redis
from app.repositories.kpi_repository import KpiRepository

settings = get_settings()
setup_logging(debug=settings.debug)
logger = logging.getLogger(__name__)


async def _periodic_kpi_refresh_loop(interval_seconds: int = 900) -> None:
    """# CONCEPT: Caching an expensive aggregate (15-min background Materialized View refresh)"""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with AsyncSessionLocal() as session:
                repo = KpiRepository(session)
                await repo.refresh_materialized_view_concurrently()
            logger.info("Scheduled 15-min REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_kpis succeeded")
        except Exception as exc:
            logger.warning("Scheduled monthly_kpis refresh skipped: %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "LeadPulse API starting | env=%s | db_host=%s | redis_host=%s | demo_ai_mode=%s",
        settings.environment,
        settings.sanitized_db_host,
        settings.sanitized_redis_host,
        settings.is_demo_ai_mode,
    )
    refresh_task = asyncio.create_task(_periodic_kpi_refresh_loop(900))
    try:
        yield
    finally:
        refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await refresh_task
        await close_redis()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "LeadPulse Mini-CRM & AI Assistant API — built to demonstrate 10 core "
            "production engineering concepts (keyset vs offset pagination, Redis + Materialized View "
            "caching, async concurrency lab, schema-constrained LLM extraction, and LLM cost controls)."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms", "Retry-After"],
    )

    # Global exception handlers (Concept 4)
    register_exception_handlers(app)

    # Routers
    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(customers.router, prefix=settings.api_v1_prefix)
    app.include_router(leads.router, prefix=settings.api_v1_prefix)
    app.include_router(kpis.router, prefix=settings.api_v1_prefix)
    app.include_router(lab.router, prefix=settings.api_v1_prefix)
    app.include_router(ai.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
