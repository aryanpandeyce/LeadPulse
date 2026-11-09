"""Repository for KPI aggregations: Materialized View `monthly_kpis` vs Raw `leads` scan.

# CONCEPT: Caching an expensive aggregate (PostgreSQL Materialized View + Raw slow path)
"""

from typing import Any

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Lead


class KpiRepository:
    """Executes KPI aggregations from either `monthly_kpis` Materialized View or raw `leads` table."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _is_postgres(self) -> bool:
        bind = self.db.get_bind()
        return bind.dialect.name == "postgresql"

    async def fetch_from_materialized_view(self) -> list[dict[str, Any]]:
        """Query pre-aggregated `monthly_kpis` Materialized View on PostgreSQL.
        In SQLite unit-test environments (where Materialized Views don't exist natively),
        runs the equivalent grouped query so tests work seamlessly.
        """
        if self._is_postgres():
            res = await self.db.execute(
                text(
                    """
                    SELECT
                        month_bucket,
                        source,
                        total_leads,
                        converted_leads,
                        lost_leads,
                        total_revenue
                    FROM monthly_kpis
                    ORDER BY month_bucket ASC, source ASC;
                    """
                )
            )
            return [
                {
                    "month_bucket": str(row.month_bucket),
                    "source": str(row.source),
                    "total_leads": int(row.total_leads),
                    "converted_leads": int(row.converted_leads),
                    "lost_leads": int(row.lost_leads),
                    "total_revenue": float(row.total_revenue),
                }
                for row in res
            ]

        return await self.fetch_raw_aggregation()

    async def fetch_raw_aggregation(self) -> list[dict[str, Any]]:
        """Slow-path raw aggregation directly scanning 200,000+ rows in `leads`."""
        if self._is_postgres():
            res = await self.db.execute(
                text(
                    """
                    SELECT
                        to_char(date_trunc('month', created_at), 'YYYY-MM') AS month_bucket,
                        source,
                        COUNT(*)::bigint AS total_leads,
                        COUNT(*) FILTER (WHERE status = 'converted')::bigint AS converted_leads,
                        COUNT(*) FILTER (WHERE status = 'lost')::bigint AS lost_leads,
                        COALESCE(SUM(revenue) FILTER (WHERE status = 'converted'), 0)::numeric(14, 2) AS total_revenue
                    FROM leads
                    GROUP BY 1, 2
                    ORDER BY 1 ASC, 2 ASC;
                    """
                )
            )
            return [
                {
                    "month_bucket": str(row.month_bucket),
                    "source": str(row.source),
                    "total_leads": int(row.total_leads),
                    "converted_leads": int(row.converted_leads),
                    "lost_leads": int(row.lost_leads),
                    "total_revenue": float(row.total_revenue),
                }
                for row in res
            ]

        # Portable SQLAlchemy expression for SQLite test runner
        month_expr = func.strftime("%Y-%m", Lead.created_at).label("month_bucket")
        stmt = (
            select(
                month_expr,
                Lead.source,
                func.count(Lead.id).label("total_leads"),
                func.sum(case((Lead.status == "converted", 1), else_=0)).label("converted_leads"),
                func.sum(case((Lead.status == "lost", 1), else_=0)).label("lost_leads"),
                func.sum(case((Lead.status == "converted", Lead.revenue), else_=0)).label(
                    "total_revenue"
                ),
            )
            .group_by(month_expr, Lead.source)
            .order_by(month_expr.asc(), Lead.source.asc())
        )
        res = await self.db.execute(stmt)
        return [
            {
                "month_bucket": str(row.month_bucket or "2026-11"),
                "source": str(row.source),
                "total_leads": int(row.total_leads or 0),
                "converted_leads": int(row.converted_leads or 0),
                "lost_leads": int(row.lost_leads or 0),
                "total_revenue": float(row.total_revenue or 0.0),
            }
            for row in res
        ]

    async def refresh_materialized_view_concurrently(self) -> None:
        """Refresh `monthly_kpis` concurrently using its unique index `(month_bucket, source)`."""
        if self._is_postgres():
            await self.db.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_kpis;")
            )
            await self.db.commit()
