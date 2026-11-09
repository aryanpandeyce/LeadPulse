"""Repository for querying and streaming the 10,000+ customers table.

# CONCEPT: Paginated, sortable, filterable table of 10,000 customers
- Strictly whitelists sortable & filterable columns via a static column map (zero SQL string interpolation).
- Uses parameterized SQLAlchemy 2.0 constructs (`ilike`, `.asc()`, `.desc()`).
- Leverages B-tree indexes on `city`, `status`, `created_at`, `total_purchase_amount` and the
  PostgreSQL `pg_trgm` GIN index `ix_customers_name_email_trgm` for fast substring search.
"""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.models.entities import Customer

# Strict whitelist mapping column name -> SQLAlchemy InstrumentedAttribute
ALLOWED_SORT_COLUMNS: dict[str, Any] = {
    "name": Customer.name,
    "email": Customer.email,
    "city": Customer.city,
    "status": Customer.status,
    "total_purchase_amount": Customer.total_purchase_amount,
    "created_at": Customer.created_at,
}

ALLOWED_STATUSES = {"active", "inactive", "churned"}


class CustomerRepository:
    """Data access layer for Customer queries."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _build_filtered_query(
        self,
        *,
        city: str | None = None,
        status: str | None = None,
        q: str | None = None,
    ) -> Select[Any]:
        stmt: Select[Any] = select(Customer)
        if city:
            stmt = stmt.where(Customer.city == city.strip())
        if status:
            normalized_status = status.strip().lower()
            if normalized_status not in ALLOWED_STATUSES:
                raise ValidationError(
                    code="INVALID_STATUS_FILTER",
                    message=f"Invalid status filter '{status}'. Allowed: {sorted(ALLOWED_STATUSES)}",
                )
            stmt = stmt.where(Customer.status == normalized_status)
        if q and q.strip():
            pattern = f"%{q.strip()}%"
            # Uses pg_trgm GIN index on Postgres and standard parameterized ILIKE everywhere
            stmt = stmt.where(
                or_(
                    Customer.name.ilike(pattern),
                    Customer.email.ilike(pattern),
                )
            )
        return stmt

    async def list_paginated(
        self,
        *,
        page: int = 1,
        limit: int = 50,
        sort_by: str = "created_at",
        order: str = "desc",
        city: str | None = None,
        status: str | None = None,
        q: str | None = None,
    ) -> tuple[list[Customer], int]:
        """Execute parameterized count + paginated select with whitelisted sorting."""
        if sort_by not in ALLOWED_SORT_COLUMNS:
            raise ValidationError(
                code="INVALID_SORT_COLUMN",
                message=f"Cannot sort by '{sort_by}'. Allowed columns: {sorted(ALLOWED_SORT_COLUMNS.keys())}",
            )
        if order not in ("asc", "desc"):
            raise ValidationError(
                code="INVALID_SORT_ORDER",
                message="Sort order must be 'asc' or 'desc'.",
            )

        base_stmt = self._build_filtered_query(city=city, status=status, q=q)

        # 1. Total matching count
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = int(total_res.scalar_one() or 0)

        # 2. Deterministic ordering (always include Customer.id tiebreaker)
        sort_col = ALLOWED_SORT_COLUMNS[sort_by]
        primary_order = sort_col.asc() if order == "asc" else sort_col.desc()
        tiebreaker_order = Customer.id.asc() if order == "asc" else Customer.id.desc()

        offset = (page - 1) * limit
        data_stmt = (
            base_stmt.order_by(primary_order, tiebreaker_order)
            .offset(offset)
            .limit(limit)
        )
        rows_res = await self.db.execute(data_stmt)
        customers: list[Customer] = list(rows_res.scalars().all())
        return customers, total

    async def stream_filtered_customers(
        self,
        *,
        sort_by: str = "created_at",
        order: str | None = "desc",
        city: str | None = None,
        status: str | None = None,
        q: str | None = None,
    ) -> AsyncIterator[Customer]:
        """Stream matching customers in chunks without loading all 10k rows into memory."""
        sort_col = ALLOWED_SORT_COLUMNS.get(sort_by, Customer.created_at)
        primary_order = sort_col.asc() if order == "asc" else sort_col.desc()
        stmt = self._build_filtered_query(city=city, status=status, q=q).order_by(
            primary_order, Customer.id.asc()
        )
        stream = await self.db.stream_scalars(stmt.execution_options(yield_per=500))
        async for customer in stream:
            cust: Customer = customer
            yield cust

