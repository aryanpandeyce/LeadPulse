"""Business logic service for Customer directory & CSV streaming export."""

from collections.abc import AsyncIterator
import csv
import io
import math
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerRead, PaginatedCustomersResponse


class CustomerService:
    """Service orchestrating customer pagination, filtering, sorting, and CSV export."""

    def __init__(self, db: AsyncSession) -> None:
        self.repo = CustomerRepository(db)

    async def get_customers_page(
        self,
        *,
        page: int = 1,
        limit: int = 50,
        sort_by: str = "name",
        order: str = "asc",
        city: str | None = None,
        status: str | None = None,
        q: str | None = None,
    ) -> PaginatedCustomersResponse:
        """Validate pagination bounds (max limit = 100) and return paginated customers."""
        if page < 1:
            raise ValidationError(
                code="INVALID_PAGE",
                message="Page number must be >= 1.",
            )
        if limit < 1 or limit > 100:
            raise ValidationError(
                code="MAX_LIMIT_EXCEEDED",
                message="Limit must be between 1 and 100.",
            )

        t0 = time.perf_counter()
        customers, total = await self.repo.list_paginated(
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order,
            city=city,
            status=status,
            q=q,
        )
        query_ms = round((time.perf_counter() - t0) * 1000, 2)
        total_pages = math.ceil(total / limit) if total > 0 else 0

        return PaginatedCustomersResponse(
            data=[CustomerRead.model_validate(c) for c in customers],
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            query_ms=query_ms,
        )

    async def export_customers_csv_stream(
        self,
        *,
        sort_by: str = "name",
        order: str = "asc",
        city: str | None = None,
        status: str | None = None,
        q: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield CSV rows asynchronously for memory-efficient export of filtered customers."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["id", "name", "email", "phone", "city", "status", "total_purchase_amount", "created_at"]
        )
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        async for c in self.repo.stream_filtered_customers(
            sort_by=sort_by, order=order, city=city, status=status, q=q
        ):
            writer.writerow(
                [
                    c.id,
                    c.name,
                    c.email,
                    c.phone,
                    c.city,
                    c.status,
                    str(c.total_purchase_amount),
                    c.created_at.isoformat(),
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)
