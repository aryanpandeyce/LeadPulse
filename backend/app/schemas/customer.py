"""Pydantic v2 schemas for Concept 2: Paginated, Sortable, Filterable Customers Table."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

SortableCustomerColumn = Literal[
    "name",
    "email",
    "city",
    "status",
    "total_purchase_amount",
    "created_at",
]
SortOrder = Literal["asc", "desc"]
CustomerStatusFilter = Literal["active", "inactive", "churned"]


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    phone: str
    city: str
    status: str
    total_purchase_amount: Decimal
    avatar_url: str
    company_logo_url: str
    created_at: datetime


class PaginatedCustomersResponse(BaseModel):
    """Canonical offset-paginated response envelope for /api/v1/customers."""

    data: list[CustomerRead]
    total: int = Field(description="Total matching rows across all pages")
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    total_pages: int = Field(ge=0)
    query_ms: float = Field(description="Server-side DB execution time in milliseconds")

