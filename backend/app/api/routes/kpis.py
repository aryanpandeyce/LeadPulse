"""Thin API routes for Concept 5: KPI Dashboard (Redis + Materialized View + Raw Slow Path + Admin Refresh)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import require_admin
from app.models.entities import User
from app.schemas.kpi import DashboardKpiResponse, KpiRefreshResponse
from app.services.kpi_service import KpiService

router = APIRouter(tags=["KPIs & Layered Caching (Concept 5)"])


@router.get(
    "/kpis",
    response_model=DashboardKpiResponse,
    summary="Fetch monthly CRM KPIs (Redis Cache-Aside -> Materialized View)",
)
async def get_dashboard_kpis(
    bypass_redis: bool = Query(
        default=False,
        description="Set true to skip Redis and measure PostgreSQL Materialized View directly",
    ),
    db: AsyncSession = Depends(get_db_session),
) -> DashboardKpiResponse:
    """# CONCEPT: Caching an expensive aggregate (Redis vs Materialized View)
    Returns `source = "redis" | "materialized_view"` and `query_ms`.
    """
    service = KpiService(db)
    return await service.get_kpis_layered(bypass_redis=bypass_redis)


@router.get(
    "/kpis/raw",
    response_model=DashboardKpiResponse,
    summary="Slow-path KPI endpoint running raw SQL GROUP BY across 200k+ leads",
)
async def get_dashboard_kpis_raw(
    db: AsyncSession = Depends(get_db_session),
) -> DashboardKpiResponse:
    """Runs the un-cached raw aggregation directly on `leads` (`source = "raw"`)."""
    service = KpiService(db)
    return await service.get_kpis_raw_slow_path()


@router.post(
    "/admin/kpis/refresh",
    response_model=KpiRefreshResponse,
    summary="Admin-only: Refresh `monthly_kpis` Materialized View concurrently and invalidate Redis",
)
async def refresh_kpis_admin(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> KpiRefreshResponse:
    """Requires `admin` role (`admin@leadpulse.io`). Refreshes MV concurrently and bumps Redis key version."""
    service = KpiService(db)
    return await service.refresh_kpis_and_invalidate_cache()

