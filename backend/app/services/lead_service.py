"""Business logic service for Lead keyset feed, offset comparison, benchmarking, and idempotent creation."""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import (
    KeysetLeadsResponse,
    LeadCreateRequest,
    LeadRead,
    OffsetLeadsResponse,
    PaginationBenchmarkPoint,
    PaginationBenchmarkResponse,
)


class LeadService:
    """Service layer for Leads (Concept 6)."""

    def __init__(self, db: AsyncSession) -> None:
        self.repo = LeadRepository(db)

    async def get_leads_keyset(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        status: str | None = None,
        source: str | None = None,
    ) -> KeysetLeadsResponse:
        if limit < 1 or limit > 100:
            raise ValidationError(
                code="MAX_LIMIT_EXCEEDED",
                message="Limit must be between 1 and 100.",
            )
        t0 = time.perf_counter()
        rows, next_cursor, has_more = await self.repo.list_keyset(
            limit=limit,
            cursor=cursor,
            status=status,
            source=source,
            include_activities=True,
        )
        query_ms = round((time.perf_counter() - t0) * 1000, 3)
        return KeysetLeadsResponse(
            data=[LeadRead.model_validate(r) for r in rows],
            next_cursor=next_cursor,
            has_more=has_more,
            query_ms=query_ms,
        )

    async def get_leads_offset(
        self,
        *,
        page: int = 1,
        limit: int = 50,
    ) -> OffsetLeadsResponse:
        if page < 1:
            raise ValidationError(code="INVALID_PAGE", message="Page must be >= 1.")
        if limit < 1 or limit > 100:
            raise ValidationError(
                code="MAX_LIMIT_EXCEEDED",
                message="Limit must be between 1 and 100.",
            )
        t0 = time.perf_counter()
        rows = await self.repo.list_offset(page=page, limit=limit, include_activities=False)
        query_ms = round((time.perf_counter() - t0) * 1000, 3)
        return OffsetLeadsResponse(
            data=[LeadRead.model_validate(r) for r in rows],
            page=page,
            limit=limit,
            offset=(page - 1) * limit,
            query_ms=query_ms,
        )

    async def run_pagination_benchmark(
        self, pages: list[int] | None = None, limit: int = 50
    ) -> PaginationBenchmarkResponse:
        """Compare Offset vs Keyset response times across pages [1, 100, 1000, 4000]."""
        target_pages = pages or [1, 100, 1000, 4000]
        total_leads = await self.repo.count_all_leads()
        points: list[PaginationBenchmarkPoint] = []

        for p in target_pages:
            requested_offset = (p - 1) * limit
            # If DB has fewer rows than requested_offset (e.g. in small unit test DB), clamp safely
            effective_offset = (
                min(requested_offset, max(0, total_leads - limit))
                if total_leads > limit
                else 0
            )
            effective_page = (effective_offset // limit) + 1

            # 1. Pre-resolve cursor outside the timed keyset window
            cursor = await self.repo.get_anchor_cursor_for_offset(effective_offset)

            # 2. Time Offset query
            t_off_start = time.perf_counter()
            await self.repo.list_offset(
                page=effective_page, limit=limit, include_activities=False
            )
            offset_ms = round((time.perf_counter() - t_off_start) * 1000, 3)

            # 3. Time Keyset query at the exact same depth
            t_key_start = time.perf_counter()
            await self.repo.list_keyset(
                limit=limit, cursor=cursor, include_activities=False
            )
            keyset_ms = round((time.perf_counter() - t_key_start) * 1000, 3)

            speedup = round(offset_ms / max(keyset_ms, 0.05), 2)
            points.append(
                PaginationBenchmarkPoint(
                    page=p,
                    offset_rows=requested_offset,
                    offset_ms=offset_ms,
                    keyset_ms=keyset_ms,
                    speedup_factor=speedup,
                )
            )

        return PaginationBenchmarkResponse(
            total_leads_in_db=total_leads,
            limit_per_page=limit,
            results=points,
        )

    async def create_lead_idempotent(
        self,
        payload: LeadCreateRequest,
        *,
        owner_id: int | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[LeadRead, bool]:
        """Create a new lead safely against double-clicks using `Idempotency-Key`.
        Returns `(LeadRead, was_replayed)`.
        """
        if idempotency_key:
            existing = await self.repo.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return LeadRead.model_validate(existing), True

        created = await self.repo.create_lead(
            customer_id=payload.customer_id,
            name=payload.name,
            email=str(payload.email),
            source=payload.source,
            status=payload.status,
            revenue=payload.revenue,
            owner_id=owner_id,
            idempotency_key=idempotency_key,
            initial_note=payload.initial_note,
        )
        return LeadRead.model_validate(created), False
