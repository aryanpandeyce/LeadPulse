"""Lead repository implementing Keyset (cursor) pagination, Offset comparison, N+1 prevention, and Idempotency.

# CONCEPT: Keyset pagination
Uses composite index `ix_leads_created_at_id_desc` on (created_at DESC, id DESC) and
SQL row-value comparison:
    WHERE (created_at, id) < (:cursor_created_at, :cursor_id)
    ORDER BY created_at DESC, id DESC
    LIMIT :limit + 1
"""

import base64
import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ValidationError
from app.models.entities import Activity, Lead


def encode_keyset_cursor(created_at: datetime, row_id: int) -> str:
    """Encode (created_at, id) into an opaque URL-safe base64 cursor."""
    payload = json.dumps({"created_at": created_at.isoformat(), "id": row_id})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_keyset_cursor(cursor: str) -> tuple[datetime, int]:
    """Decode base64 cursor back into (datetime, int), raising ValidationError on tampering."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        data: dict[str, Any] = json.loads(raw)
        created_at = datetime.fromisoformat(str(data["created_at"]))
        row_id = int(data["id"])
        return created_at, row_id
    except Exception as exc:
        raise ValidationError(
            code="INVALID_CURSOR",
            message="Provided pagination cursor is malformed or expired.",
        ) from exc


class LeadRepository:
    """Data access layer for Leads (200,000+ rows)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_keyset(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        status: str | None = None,
        source: str | None = None,
        include_activities: bool = True,
    ) -> tuple[list[Lead], str | None, bool]:
        """# CONCEPT: Keyset pagination
        Fetch `limit + 1` rows ordered by `(created_at DESC, id DESC)` using row-value comparison
        `WHERE (created_at, id) < (:cursor_ts, :cursor_id)`.
        Also uses `selectinload(Lead.activities)` to prevent N+1 queries!
        """
        stmt = select(Lead)
        if include_activities:
            # Avoid N+1 queries by eager-loading activities in a single IN (...) query
            stmt = stmt.options(selectinload(Lead.activities))
        if status:
            stmt = stmt.where(Lead.status == status)
        if source:
            stmt = stmt.where(Lead.source == source)

        if cursor:
            cursor_dt, cursor_id = decode_keyset_cursor(cursor)
            # Row-value comparison: uses composite index (created_at DESC, id DESC) directly
            stmt = stmt.where(
                tuple_(Lead.created_at, Lead.id)
                < tuple_(literal(cursor_dt), literal(cursor_id))
            )

        stmt = stmt.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(limit + 1)
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = (
            encode_keyset_cursor(items[-1].created_at, items[-1].id)
            if (has_more and items)
            else None
        )
        return items, next_cursor, has_more

    async def list_offset(
        self,
        *,
        page: int = 1,
        limit: int = 50,
        include_activities: bool = False,
    ) -> list[Lead]:
        """Offset-based pagination endpoint kept intentionally to benchmark deep OFFSET slowdown."""
        offset = (page - 1) * limit
        stmt = select(Lead)
        if include_activities:
            stmt = stmt.options(selectinload(Lead.activities))
        stmt = (
            stmt.order_by(Lead.created_at.desc(), Lead.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_anchor_cursor_for_offset(self, offset_rows: int) -> str | None:
        """Find the `(created_at, id)` at `offset_rows` depth so the benchmark can compare
        Keyset vs Offset at the exact same position in the dataset.
        """
        if offset_rows <= 0:
            return None
        stmt = (
            select(Lead.created_at, Lead.id)
            .order_by(Lead.created_at.desc(), Lead.id.desc())
            .offset(offset_rows - 1)
            .limit(1)
        )
        res = await self.db.execute(stmt)
        row = res.first()
        if not row:
            return None
        return encode_keyset_cursor(row[0], int(row[1]))

    async def count_all_leads(self) -> int:
        res = await self.db.execute(select(func.count(Lead.id)))
        return int(res.scalar_one() or 0)

    async def get_by_idempotency_key(self, key: str) -> Lead | None:
        stmt = (
            select(Lead)
            .options(selectinload(Lead.activities))
            .where(Lead.idempotency_key == key)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def create_lead(
        self,
        *,
        customer_id: int | None,
        name: str,
        email: str,
        source: str,
        status: str,
        revenue: Any,
        owner_id: int | None,
        idempotency_key: str | None,
        initial_note: str | None,
    ) -> Lead:
        lead = Lead(
            customer_id=customer_id,
            name=name,
            email=email,
            source=source,
            status=status,
            revenue=revenue,
            owner_id=owner_id,
            idempotency_key=idempotency_key,
        )
        self.db.add(lead)
        await self.db.flush()

        if initial_note:
            act = Activity(
                lead_id=lead.id,
                type="note",
                message=initial_note,
            )
            self.db.add(act)

        await self.db.commit()
        stmt = (
            select(Lead)
            .options(selectinload(Lead.activities))
            .where(Lead.id == lead.id)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one()
