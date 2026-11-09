"""Service implementing Two-Layer KPI Caching (Redis Cache-Aside + Materialized View + Stampede Lock).

# CONCEPT: Caching an expensive aggregate (Redis vs Materialized View)
1. Layer 1 (Redis Cache-Aside): Versioned key `kpis:monthly:v{version}` with TTL = 300s.
   Protected against cache stampede via an async lock + Redis NX lock (`lock:kpis:monthly`).
2. Layer 2 (PostgreSQL Materialized View `monthly_kpis`): Pre-aggregated monthly buckets,
   refreshed every 15 minutes in the background and on-demand via `POST /api/v1/admin/kpis/refresh`.
3. Slow Path (`GET /api/v1/kpis/raw`): Directly aggregates 200,000+ rows in `leads` for comparison.
"""

import asyncio
import json
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.repositories.kpi_repository import KpiRepository
from app.schemas.kpi import (
    DashboardKpiResponse,
    KpiRefreshResponse,
    KpiSourceType,
    LeadsBySourceItem,
    MonthlyTrendPoint,
)

settings = get_settings()
KPI_VERSION_KEY = "kpis:version"
_local_stampede_lock = asyncio.Lock()


class KpiService:
    """Orchestrates layered KPI caching, stampede protection, and view refreshes."""

    def __init__(self, db: AsyncSession) -> None:
        self.repo = KpiRepository(db)

    async def _get_cache_version(self) -> int:
        redis = await get_redis()
        val = await redis.get(KPI_VERSION_KEY)
        if val is None:
            await redis.set(KPI_VERSION_KEY, "1")
            return 1
        return int(val)

    def _assemble_dashboard_payload(
        self,
        rows: list[dict[str, Any]],
        *,
        source: KpiSourceType,
        query_ms: float,
        version: int,
    ) -> DashboardKpiResponse:
        total_leads = 0
        converted_leads = 0
        lost_leads = 0
        total_revenue = 0.0

        by_source_map: dict[str, dict[str, float | int]] = {}
        by_month_map: dict[str, dict[str, float | int]] = {}

        for r in rows:
            m = r["month_bucket"]
            s = r["source"]
            tl = int(r["total_leads"])
            cl = int(r["converted_leads"])
            ll = int(r["lost_leads"])
            rev = float(r["total_revenue"])

            total_leads += tl
            converted_leads += cl
            lost_leads += ll
            total_revenue += rev

            src_bucket = by_source_map.setdefault(
                s, {"total_leads": 0, "converted_leads": 0, "revenue": 0.0}
            )
            src_bucket["total_leads"] = int(src_bucket["total_leads"]) + tl
            src_bucket["converted_leads"] = int(src_bucket["converted_leads"]) + cl
            src_bucket["revenue"] = float(src_bucket["revenue"]) + rev

            m_bucket = by_month_map.setdefault(
                m,
                {
                    "total_leads": 0,
                    "converted_leads": 0,
                    "lost_leads": 0,
                    "revenue": 0.0,
                },
            )
            m_bucket["total_leads"] = int(m_bucket["total_leads"]) + tl
            m_bucket["converted_leads"] = int(m_bucket["converted_leads"]) + cl
            m_bucket["lost_leads"] = int(m_bucket["lost_leads"]) + ll
            m_bucket["revenue"] = float(m_bucket["revenue"]) + rev

        conv_pct = round((converted_leads / total_leads) * 100, 2) if total_leads > 0 else 0.0

        leads_by_source = [
            LeadsBySourceItem(
                source=src,
                total_leads=int(vals["total_leads"]),
                converted_leads=int(vals["converted_leads"]),
                revenue=round(float(vals["revenue"]), 2),
            )
            for src, vals in sorted(by_source_map.items())
        ]

        monthly_trend: list[MonthlyTrendPoint] = []
        for month_key in sorted(by_month_map.keys()):
            mv = by_month_map[month_key]
            m_tot = int(mv["total_leads"])
            m_conv = int(mv["converted_leads"])
            m_pct = round((m_conv / m_tot) * 100, 2) if m_tot > 0 else 0.0
            monthly_trend.append(
                MonthlyTrendPoint(
                    month=month_key,
                    total_leads=m_tot,
                    converted_leads=m_conv,
                    lost_leads=int(mv["lost_leads"]),
                    revenue=round(float(mv["revenue"]), 2),
                    conversion_rate_pct=m_pct,
                )
            )

        return DashboardKpiResponse(
            source=source,
            query_ms=query_ms,
            cache_key_version=version,
            total_leads=total_leads,
            converted_leads=converted_leads,
            lost_leads=lost_leads,
            total_revenue=round(total_revenue, 2),
            conversion_rate_pct=conv_pct,
            leads_by_source=leads_by_source,
            monthly_trend=monthly_trend,
        )

    async def get_kpis_layered(self, bypass_redis: bool = False) -> DashboardKpiResponse:
        """# CONCEPT: Caching an expensive aggregate (Cache-aside + Stampede Coalescing)
        1. Check Redis versioned key `kpis:monthly:v{version}`.
        2. On miss, acquire stampede lock so 50 concurrent dashboard requests don't all hit Postgres.
        3. Query `monthly_kpis` Materialized View, populate Redis with TTL=300s, and return.
        """
        t0 = time.perf_counter()
        redis = await get_redis()
        version = await self._get_cache_version()
        cache_key = f"kpis:monthly:v{version}"

        if not bypass_redis:
            cached_raw = await redis.get(cache_key)
            if cached_raw:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
                payload = json.loads(cached_raw)
                payload["source"] = "redis"
                payload["query_ms"] = elapsed_ms
                return DashboardKpiResponse.model_validate(payload)

        # Cache miss -> coalesce concurrent requests using stampede lock
        async with _local_stampede_lock:
            if not bypass_redis:
                second_check = await redis.get(cache_key)
                if second_check:
                    elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
                    payload = json.loads(second_check)
                    payload["source"] = "redis"
                    payload["query_ms"] = elapsed_ms
                    return DashboardKpiResponse.model_validate(payload)

            rows = await self.repo.fetch_from_materialized_view()
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
            response = self._assemble_dashboard_payload(
                rows,
                source="materialized_view",
                query_ms=elapsed_ms,
                version=version,
            )
            await redis.set(
                cache_key,
                response.model_dump_json(),
                ex=settings.kpi_cache_ttl_seconds,
            )
            return response

    async def get_kpis_raw_slow_path(self) -> DashboardKpiResponse:
        """Directly aggregate on the 200,000+ `leads` table without Redis or Materialized View."""
        t0 = time.perf_counter()
        version = await self._get_cache_version()
        rows = await self.repo.fetch_raw_aggregation()
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
        return self._assemble_dashboard_payload(
            rows,
            source="raw",
            query_ms=elapsed_ms,
            version=version,
        )

    async def refresh_kpis_and_invalidate_cache(self) -> KpiRefreshResponse:
        """Refresh `monthly_kpis` concurrently and increment the versioned Redis key for instant invalidation."""
        t0 = time.perf_counter()
        await self.repo.refresh_materialized_view_concurrently()
        redis = await get_redis()
        new_version = int(await redis.incr(KPI_VERSION_KEY))
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
        return KpiRefreshResponse(
            status="ok",
            refreshed_view="monthly_kpis",
            new_cache_version=new_version,
            elapsed_ms=elapsed_ms,
        )
