"""SQLAlchemy 2.0 ORM Models for LeadPulse CRM.

Tables:
- users (admin & agent roles, bcrypt password hashes)
- customers (10,000 rows, B-tree + composite + pg_trgm GIN indexes)
- leads (200,000+ rows, keyset composite index on created_at DESC, id DESC + idempotency_key)
- activities (500,000 rows, indexed on lead_id + created_at)
- products (product catalog with optimized image URLs for Concept 1)
- llm_usage (tracks every LLM call: tokens, cost_usd, model, feature, cache_hit for Concept 8)
- knowledge_base_docs (chunks for RAG-lite retrieval in Concept 8)
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
     Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="agent", nullable=False)  # admin | agent
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Customer(Base):
    """Customer record (10,000 rows seeded).

    # CONCEPT: Paginated, sortable, filterable table of 10,000 customers
    Indexed for fast filtering by city/status, sorting by total_purchase_amount/created_at,
    and fuzzy search on name/email via pg_trgm GIN index in Alembic migration.
    """

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False
    )  # active | inactive | churned
    total_purchase_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=False)
    company_logo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="customer")

    __table_args__ = (
        Index("ix_customers_city", "city"),
        Index("ix_customers_status", "status"),
        Index("ix_customers_created_at", "created_at"),
        Index("ix_customers_total_purchase_amount", "total_purchase_amount"),
        Index("ix_customers_status_city_amount", "status", "city", "total_purchase_amount"),
    )


class Lead(Base):
    """Lead record (200,000+ rows seeded).

    # CONCEPT: Keyset pagination
    Composite index `ix_leads_created_at_id_desc` on (created_at DESC, id DESC) powers
    O(1) cursor pagination using row-value comparison WHERE (created_at, id) < (:created_at, :id).
    """

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # website | referral | linkedin | cold_outreach | event
    status: Mapped[str] = mapped_column(
        String(32), default="new", nullable=False, index=True
    )  # new | contacted | qualified | converted | lost
    revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    customer: Mapped[Customer | None] = relationship("Customer", back_populates="leads")
    activities: Mapped[list["Activity"]] = relationship(
        "Activity", back_populates="lead", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_leads_created_at_id_desc", created_at.desc(), id.desc()),
        Index("ix_leads_created_at_status", "created_at", "status"),
    )


class Activity(Base):
    """Activity log on a lead (500,000 rows seeded)."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # call | email | note | status_change
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    lead: Mapped[Lead] = relationship("Lead", back_populates="activities")


class Product(Base):
    """Product catalog item (used in CRM and Concept 1 Next.js <Image> optimization)."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class LLMUsage(Base):
    """Granular audit log of every AI interaction for cost control and budgeting.

    # CONCEPT: Controlling LLM cost in production (Usage tracking & daily budgets)
    """

    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    feature: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # smart_lead_capture | ai_assistant
    model: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0.000000"), nullable=False
    )
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )


class KnowledgeBaseDoc(Base):
    """Knowledge base document chunks for RAG-lite retrieval in the AI Assistant.

    # CONCEPT: Controlling LLM cost in production (RAG-lite top-k chunk retrieval)
    """

    __tablename__ = "knowledge_base_docs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str] = mapped_column(String(400), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
