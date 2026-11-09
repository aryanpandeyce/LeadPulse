"""Pydantic v2 schemas for Concept 6: Keyset (Cursor) vs Offset Pagination on 200k+ Leads + Idempotent Lead Creation."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

LeadStatus = Literal["new", "contacted", "qualified", "converted", "lost"]
LeadSource = Literal["website", "referral", "linkedin", "cold_outreach", "event"]


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    type: str
    message: str
    created_at: datetime


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int | None = None
    name: str
    email: EmailStr
    source: str
    status: str
    revenue: Decimal
    owner_id: int | None = None
    idempotency_key: str | None = None
    created_at: datetime
    activities: list[ActivityRead] = Field(default_factory=list)


class LeadCreateRequest(BaseModel):
    customer_id: int | None = None
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    source: LeadSource = "website"
    status: LeadStatus = "new"
    revenue: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    initial_note: str | None = Field(default=None, max_length=500)


class KeysetLeadsResponse(BaseModel):
    """Canonical keyset (cursor) pagination response for /api/v1/leads."""

    data: list[LeadRead]
    next_cursor: str | None = Field(
        default=None,
        description="Opaque base64-encoded JSON cursor of the last row's (created_at, id)",
    )
    has_more: bool
    query_ms: float


class OffsetLeadsResponse(BaseModel):
    """Offset-based pagination response for /api/v1/leads/offset (comparison endpoint)."""

    data: list[LeadRead]
    page: int
    limit: int
    offset: int
    query_ms: float


class PaginationBenchmarkPoint(BaseModel):
    page: int
    offset_rows: int
    offset_ms: float
    keyset_ms: float
    speedup_factor: float


class PaginationBenchmarkResponse(BaseModel):
    total_leads_in_db: int
    limit_per_page: int
    results: list[PaginationBenchmarkPoint]

