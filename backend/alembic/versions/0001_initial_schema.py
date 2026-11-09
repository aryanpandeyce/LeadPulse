"""Initial schema, B-tree/composite indexes, pg_trgm GIN search index, keyset index, and monthly_kpis materialized view.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        # Enable pg_trgm for fast substring/ILIKE search on customers (Concept 2)
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="agent"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. customers
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "total_purchase_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("avatar_url", sa.String(length=500), nullable=False),
        sa.Column("company_logo_url", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    # CONCEPT: Paginated, sortable, filterable table of 10,000 customers (B-tree + Composite + pg_trgm GIN indexes)
    op.create_index("ix_customers_city", "customers", ["city"])
    op.create_index("ix_customers_status", "customers", ["status"])
    op.create_index("ix_customers_created_at", "customers", ["created_at"])
    op.create_index("ix_customers_total_purchase_amount", "customers", ["total_purchase_amount"])
    op.create_index(
        "ix_customers_status_city_amount",
        "customers",
        ["status", "city", "total_purchase_amount"],
    )

    if is_postgres:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_customers_name_email_trgm "
            "ON customers USING gin ((name || ' ' || email) gin_trgm_ops);"
        )

    # 3. leads
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column(
            "revenue", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00"
        ),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_leads_customer_id", "leads", ["customer_id"])
    op.create_index("ix_leads_email", "leads", ["email"])
    op.create_index("ix_leads_source", "leads", ["source"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_owner_id", "leads", ["owner_id"])
    op.create_index("ix_leads_created_at_status", "leads", ["created_at", "status"])

    # CONCEPT: Keyset pagination — Composite index on (created_at DESC, id DESC)
    if is_postgres:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_leads_created_at_id_desc "
            "ON leads (created_at DESC, id DESC);"
        )
    else:
        op.create_index("ix_leads_created_at_id_desc", "leads", ["created_at", "id"])

    # 4. activities
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activities_lead_id", "activities", ["lead_id"])
    op.create_index("ix_activities_created_at", "activities", ["created_at"])

    # 5. products
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku"),
    )

    # 6. llm_usage
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("feature", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
            server_default="0.000000",
        ),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usage_user_id", "llm_usage", ["user_id"])
    op.create_index("ix_llm_usage_feature", "llm_usage", ["feature"])
    op.create_index("ix_llm_usage_model", "llm_usage", ["model"])
    op.create_index("ix_llm_usage_cache_hit", "llm_usage", ["cache_hit"])
    op.create_index("ix_llm_usage_created_at", "llm_usage", ["created_at"])

    # 7. knowledge_base_docs
    op.create_table(
        "knowledge_base_docs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords", sa.String(length=400), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_knowledge_base_docs_category", "knowledge_base_docs", ["category"])

    # CONCEPT: Caching an expensive aggregate (PostgreSQL Materialized View with UNIQUE index for CONCURRENT refresh)
    if is_postgres:
        op.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_kpis AS
            SELECT
                to_char(date_trunc('month', created_at), 'YYYY-MM') AS month_bucket,
                source,
                COUNT(*)::bigint AS total_leads,
                COUNT(*) FILTER (WHERE status = 'converted')::bigint AS converted_leads,
                COUNT(*) FILTER (WHERE status = 'lost')::bigint AS lost_leads,
                COALESCE(SUM(revenue) FILTER (WHERE status = 'converted'), 0)::numeric(14, 2) AS total_revenue
            FROM leads
            GROUP BY 1, 2;
            """
        )
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_monthly_kpis_month_source
            ON monthly_kpis (month_bucket, source);
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("DROP MATERIALIZED VIEW IF EXISTS monthly_kpis;")

    op.drop_table("knowledge_base_docs")
    op.drop_table("llm_usage")
    op.drop_table("products")
    op.drop_table("activities")
    op.drop_table("leads")
    op.drop_table("customers")
    op.drop_table("users")

