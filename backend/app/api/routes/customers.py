"""Thin API routes for Concept 2: Paginated, Sortable, Filterable Table of 10,000 Customers."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.customer import PaginatedCustomersResponse
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers (Concept 2: 10k Server Table)"])


@router.get(
    "",
    response_model=PaginatedCustomersResponse,
    summary="List customers with server-side pagination, whitelisted sorting, and pg_trgm search",
)
async def list_customers(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    limit: int = Query(default=50, description="Rows per page (max 100)"),
    sort_by: str = Query(
        default="name",
        description="Whitelisted sort column: name | email | city | status | total_purchase_amount | created_at",
    ),
    order: str = Query(default="asc", description="Sort direction: asc | desc"),
    city: str | None = Query(default=None, description="Exact city filter (e.g., Ahmedabad)"),
    status: str | None = Query(
        default=None, description="Status filter: active | inactive | churned"
    ),
    q: str | None = Query(
        default=None, description="Fuzzy search across name and email (powered by pg_trgm GIN index)"
    ),
    db: AsyncSession = Depends(get_db_session),
) -> PaginatedCustomersResponse:
    """# CONCEPT: Paginated, sortable, filterable table of 10,000 customers
    Never loads all 10,000 rows in the browser. Enforces column whitelisting and max limit = 100.
    """
    service = CustomerService(db)
    return await service.get_customers_page(
        page=page,
        limit=limit,
        sort_by=sort_by,
        order=order,
        city=city,
        status=status,
        q=q,
    )


@router.get(
    "/export.csv",
    summary="Stream filtered customers as CSV without buffering all rows in memory",
)
async def export_customers_csv(
    sort_by: str = Query(default="name"),
    order: str = Query(default="asc"),
    city: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream matching customers directly from async SQLAlchemy cursor to HTTP response."""
    service = CustomerService(db)
    return StreamingResponse(
        service.export_customers_csv_stream(
            sort_by=sort_by, order=order, city=city, status=status, q=q
        ),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leadpulse_customers.csv"'},
    )
