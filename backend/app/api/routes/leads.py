"""Thin API route handlers for Concept 6: Keyset vs Offset Pagination & Idempotent Lead Creation."""

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import get_optional_user
from app.models.entities import User
from app.schemas.lead import (
    KeysetLeadsResponse,
    LeadCreateRequest,
    LeadRead,
    OffsetLeadsResponse,
    PaginationBenchmarkResponse,
)
from app.services.lead_service import LeadService

router = APIRouter(prefix="/leads", tags=["Leads (Concept 6: Keyset vs Offset Pagination)"])


@router.get(
    "",
    response_model=KeysetLeadsResponse,
    summary="List leads using O(1) Keyset (Cursor) Pagination on (created_at DESC, id DESC)",
)
async def list_leads_keyset(
    limit: int = Query(default=50, description="Number of leads to fetch (max 100)"),
    cursor: str | None = Query(
        default=None,
        description="Opaque base64-encoded JSON cursor of the previous page's last (created_at, id)",
    ),
    status: str | None = Query(default=None, description="Optional status filter"),
    source: str | None = Query(default=None, description="Optional source filter"),
    db: AsyncSession = Depends(get_db_session),
) -> KeysetLeadsResponse:
    """# CONCEPT: Keyset pagination
    Uses `WHERE (created_at, id) < (:created_at, :id)` backed by `ix_leads_created_at_id_desc`.
    """
    service = LeadService(db)
    return await service.get_leads_keyset(
        limit=limit,
        cursor=cursor,
        status=status,
        source=source,
    )


@router.get(
    "/offset",
    response_model=OffsetLeadsResponse,
    summary="List leads using traditional OFFSET/LIMIT (for benchmark comparison with Keyset)",
)
async def list_leads_offset(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    limit: int = Query(default=50, description="Rows per page (max 100)"),
    db: AsyncSession = Depends(get_db_session),
) -> OffsetLeadsResponse:
    """Demonstrates O(N) deep OFFSET slowdown at high page numbers (e.g. page 4000 = OFFSET 199950)."""
    service = LeadService(db)
    return await service.get_leads_offset(page=page, limit=limit)


@router.get(
    "/benchmark",
    response_model=PaginationBenchmarkResponse,
    summary="Run live benchmark comparing Offset vs Keyset at pages 1, 100, 1000, and 4000",
)
async def benchmark_pagination(
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> PaginationBenchmarkResponse:
    """Executes both pagination strategies at pages 1, 100, 1000, and 4000 and returns timings."""
    service = LeadService(db)
    return await service.run_pagination_benchmark(pages=[1, 100, 1000, 4000], limit=limit)


@router.post(
    "",
    response_model=LeadRead,
    status_code=201,
    summary="Create a new lead safely with Idempotency-Key support",
)
async def create_lead(
    payload: LeadCreateRequest,
    response: Response,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Optional unique key to make POST /leads safe against double-clicks or network retries",
    ),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> LeadRead:
    """Creates a lead or replays the previously created lead if `Idempotency-Key` was already processed."""
    service = LeadService(db)
    lead, was_replayed = await service.create_lead_idempotent(
        payload,
        owner_id=current_user.id if current_user else None,
        idempotency_key=idempotency_key,
    )
    response.headers["X-Idempotent-Replay"] = "true" if was_replayed else "false"
    if was_replayed:
        response.status_code = 200
    return lead
