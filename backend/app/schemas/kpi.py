"""Pydantic v2 schemas for Concept 5: Caching an Expensive Aggregate (Redis + Materialized View + Raw)."""

from typing import Literal

from pydantic import BaseModel, Field

KpiSourceType = Literal["redis", "materialized_view", "raw"]


class LeadsBySourceItem(BaseModel):
    source: str
    total_leads: int
    converted_leads: int
    revenue: float


class MonthlyTrendPoint(BaseModel):
    month: str
    total_leads: int
    converted_leads: int
    lost_leads: int
    revenue: float
    conversion_rate_pct: float


class DashboardKpiResponse(BaseModel):
    """Dashboard KPI payload with observability debug badge fields (`source` & `query_ms`)."""

    source: KpiSourceType = Field(
        description="Data source that served this response: redis | materialized_view | raw"
    )
    query_ms: float = Field(description="Execution latency in milliseconds")
    cache_key_version: int = Field(default=1)
    total_leads: int
    converted_leads: int
    lost_leads: int
    total_revenue: float
    conversion_rate_pct: float
    leads_by_source: list[LeadsBySourceItem]
    monthly_trend: list[MonthlyTrendPoint]


class KpiRefreshResponse(BaseModel):
    status: str
    refreshed_view: str
    new_cache_version: int
    elapsed_ms: float
