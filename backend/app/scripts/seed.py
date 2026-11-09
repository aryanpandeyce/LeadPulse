"""High-speed bulk seeding script for LeadPulse CRM.

Creates by default:
- 2 demo users (`admin@leadpulse.io` / `Admin@123` and `agent@leadpulse.io` / `Agent@123`)
- 10,000 customers (with realistic cities, statuses, purchase amounts, and optimized image URLs)
- 200,000 leads (configurable up to 1,000,000 via `--leads`)
- 500,000 activities (configurable via `--activities`)
- 12 products & 8 knowledge base documents (for RAG-lite in Concept 8)
- Sample LLM usage logs (so `/admin/ai-costs` has rich historical charts out of the box)

Uses batched bulk inserts (`insert(Model)` in chunks of 5,000-10,000 rows) for speed and low memory usage.
"""

import argparse
import asyncio
import random
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from faker import Faker
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import hash_password
from app.models.entities import (
    Activity,
    Customer,
    KnowledgeBaseDoc,
    Lead,
    LLMUsage,
    Product,
    User,
)

CITIES = [
    "Ahmedabad",
    "Bengaluru",
    "Mumbai",
    "Delhi",
    "Pune",
    "Hyderabad",
    "Chennai",
    "Kolkata",
    "Surat",
    "Jaipur",
]
CUSTOMER_STATUSES = ["active", "active", "active", "inactive", "churned"]
LEAD_SOURCES = ["website", "referral", "linkedin", "cold_outreach", "event"]
LEAD_STATUSES = ["new", "contacted", "qualified", "converted", "lost"]
ACTIVITY_TYPES = ["call", "email", "note", "status_change"]
ACTIVITY_MESSAGES = [
    "Initial discovery call completed; prospect requested pricing breakdown.",
    "Sent follow-up product deck and case study PDF.",
    "Qualified budget and Q4 timeline with decision maker.",
    "Updated lead stage after live product walkthrough.",
    "Left voicemail regarding enterprise onboarding SLA.",
]


async def ensure_tables_exist() -> None:
    """Ensure all tables (and Materialized View on Postgres) exist before seeding."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_customers_name_email_trgm "
                    "ON customers USING gin ((name || ' ' || email) gin_trgm_ops);"
                )
            )
            await conn.execute(
                text(
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
            )
            await conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_monthly_kpis_month_source
                    ON monthly_kpis (month_bucket, source);
                    """
                )
            )


async def seed_database(
    session: AsyncSession,
    *,
    num_customers: int = 10_000,
    num_leads: int = 200_000,
    num_activities: int = 500_000,
    reset: bool = True,
) -> dict[str, Any]:
    """Populate database with deterministic, realistic CRM data."""
    t0 = time.perf_counter()
    fake = Faker()
    Faker.seed(42)
    random.seed(42)

    if reset:
        await session.execute(delete(Activity))
        await session.execute(delete(Lead))
        await session.execute(delete(Customer))
        await session.execute(delete(LLMUsage))
        await session.execute(delete(KnowledgeBaseDoc))
        await session.execute(delete(Product))
        await session.execute(delete(User))
        await session.commit()

    # 1. Seed Users (admin + agent)
    from app.core.config import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    admin_user = User(
        email="admin@leadpulse.io",
        full_name="Aryan Pandey (Admin)",
        hashed_password=hash_password(settings.seed_admin_password),
        role="admin",
        is_active=True,
        created_at=now,
    )
    agent_user = User(
        email="agent@leadpulse.io",
        full_name="Priya Sharma (Sales Agent)",
        hashed_password=hash_password(settings.seed_agent_password),
        role="agent",
        is_active=True,
        created_at=now,
    )
    session.add_all([admin_user, agent_user])
    await session.commit()
    await session.refresh(admin_user)
    await session.refresh(agent_user)
    user_ids = [admin_user.id, agent_user.id]

    # 2. Seed Products (Concept 1 next/image catalog)
    product_rows = [
        {
            "name": f"LeadPulse {tier} Plan",
            "sku": f"LP-PLAN-{idx:03d}",
            "category": "SaaS Subscription",
            "price": Decimal(str(49 * idx)),
            "image_url": f"https://picsum.photos/seed/leadpulse-prod-{idx}/600/400",
            "description": f"Enterprise CRM module #{idx} with automated lead routing and AI insights.",
            "created_at": now,
        }
        for idx, tier in enumerate(
            [
                "Starter",
                "Growth",
                "Scale",
                "Enterprise",
                "AI Copilot",
                "Analytics Pro",
                "WhatsApp Bridge",
                "Voice Intelligence",
                "Pipeline Guard",
                "RevOps Suite",
                "Data Enrich",
                "Custom SLA",
            ],
            start=1,
        )
    ]
    await session.execute(insert(Product), product_rows)

    # 3. Seed Knowledge Base Docs (Concept 8 RAG-lite)
    kb_docs = [
        {
            "slug": "pricing-tiers",
            "title": "LeadPulse Pricing & Plans",
            "category": "pricing",
            "content": "LeadPulse offers 3 core tiers: Starter ($49/month for up to 5 seats), Growth ($149/month for 20 seats + Smart Lead Capture), and Enterprise ($499/month with unlimited seats, SSO, custom SLA, and dedicated Postgres instance).",
            "keywords": "price pricing cost plan starter growth enterprise subscription monthly",
            "created_at": now,
        },
        {
            "slug": "smart-lead-capture",
            "title": "How Smart Lead Capture Works",
            "category": "features",
            "content": "Smart Lead Capture uses schema-constrained LLM tool-use (Pydantic v2 JSON schema) to extract structured lead fields (name, email, phone, city, budget, urgency, confidence) from unstructured WhatsApp messages or emails with up to 2 automatic validation retries.",
            "keywords": "smart lead capture extract json whatsapp email pydantic llm retry urgency",
            "created_at": now,
        },
        {
            "slug": "keyset-pagination-guide",
            "title": "Why LeadPulse Uses Keyset Pagination for the Leads Feed",
            "category": "architecture",
            "content": "Offset pagination (OFFSET 100000 LIMIT 50) forces PostgreSQL to scan and discard 100,000 rows. LeadPulse uses keyset cursor pagination with WHERE (created_at, id) < (:cursor_ts, :cursor_id) backed by a composite index (created_at DESC, id DESC) for constant O(1) sub-5ms latency at any depth.",
            "keywords": "pagination keyset cursor offset performance leads feed index",
            "created_at": now,
        },
        {
            "slug": "kpi-caching-architecture",
            "title": "KPI Dashboard Two-Layer Caching (Redis + Materialized View)",
            "category": "architecture",
            "content": "Monthly KPIs are pre-aggregated in the `monthly_kpis` PostgreSQL Materialized View (refreshed concurrently every 15 minutes or on admin demand) and cached in Redis for 300 seconds with versioned keys and a stampede lock.",
            "keywords": "cache caching redis materialized view kpi dashboard refresh stampede",
            "created_at": now,
        },
        {
            "slug": "security-and-rbac",
            "title": "Authentication, JWT Refresh & Role-Based Access Control",
            "category": "security",
            "content": "LeadPulse uses bcrypt password hashing, short-lived JWT access tokens (30 min), rotating refresh tokens (7 days), and two roles: `admin` (can refresh KPIs and inspect AI cost analytics) and `agent` (standard CRM operations).",
            "keywords": "security auth jwt token refresh admin agent role rbac bcrypt",
            "created_at": now,
        },
        {
            "slug": "llm-cost-controls",
            "title": "Production LLM Cost Control Levers",
            "category": "ai",
            "content": "LeadPulse controls AI spend via 10 levers: (1) Model routing between cheap gpt-4o-mini and strong gpt-4o, (2) FAQ zero-LLM short-circuiting, (3) Normalized prompt Redis caching, (4) Token history trimming, (5) RAG-lite top-3 chunk retrieval, (6) Per-user rate limiting (20 req/min), (7) Usage logging in llm_usage, and (8) Daily per-user spend caps ($1.00/day).",
            "keywords": "llm cost control budget rate limit cache routing rag token spend",
            "created_at": now,
        },
    ]
    await session.execute(insert(KnowledgeBaseDoc), kb_docs)
    await session.commit()

    # 4. Seed Customers (10,000 by default) in batches of 2,500
    first_names = [fake.first_name() for _ in range(250)]
    last_names = [fake.last_name() for _ in range(250)]

    batch_size_cust = 2500
    for start_idx in range(1, num_customers + 1, batch_size_cust):
        end_idx = min(start_idx + batch_size_cust, num_customers + 1)
        cust_batch: list[dict[str, Any]] = []
        for i in range(start_idx, end_idx):
            fname = first_names[i % len(first_names)]
            lname = last_names[(i * 7) % len(last_names)]
            full_name = "Aryan Sharma" if i <= 5 else f"{fname} {lname}"
            city = CITIES[i % len(CITIES)]
            status = CUSTOMER_STATUSES[i % len(CUSTOMER_STATUSES)]
            created_at = now - timedelta(days=i % 365, minutes=i % 1440)
            cust_batch.append(
                {
                    "name": full_name,
                    "email": f"customer.{i}.{fname.lower()}@example.com",
                    "phone": f"+91-98{i % 100000000:08d}",
                    "city": city,
                    "status": status,
                    "total_purchase_amount": Decimal(f"{((i * 137) % 95000) + 500}.00"),
                    "avatar_url": f"https://picsum.photos/seed/cust-avatar-{(i % 200) + 1}/120/120",
                    "company_logo_url": f"https://picsum.photos/seed/comp-logo-{(i % 100) + 1}/120/120",
                    "created_at": created_at,
                }
            )
        await session.execute(insert(Customer), cust_batch)
        await session.commit()

    # Fetch first customer ID to offset foreign keys cleanly
    min_cust_id_res = await session.execute(select(func.min(Customer.id)))
    min_cust_id = int(min_cust_id_res.scalar_one() or 1)

    # 5. Seed Leads (200,000 by default, configurable up to 1,000,000) in batches of 10,000
    batch_size_leads = 10_000
    for start_idx in range(1, num_leads + 1, batch_size_leads):
        end_idx = min(start_idx + batch_size_leads, num_leads + 1)
        lead_batch: list[dict[str, Any]] = []
        for i in range(start_idx, end_idx):
            status = LEAD_STATUSES[i % len(LEAD_STATUSES)]
            source = LEAD_SOURCES[i % len(LEAD_SOURCES)]
            revenue = (
                Decimal(f"{((i * 293) % 45000) + 1200}.00")
                if status == "converted"
                else Decimal("0.00")
            )
            created_at = now - timedelta(seconds=i * 60)
            lead_batch.append(
                {
                    "customer_id": min_cust_id + (i % num_customers),
                    "name": f"Lead #{i} ({first_names[i % len(first_names)]} {last_names[(i * 3) % len(last_names)]})",
                    "email": f"lead.{i}@prospect.io",
                    "source": source,
                    "status": status,
                    "revenue": revenue,
                    "owner_id": user_ids[i % len(user_ids)],
                    "idempotency_key": None,
                    "created_at": created_at,
                }
            )
        await session.execute(insert(Lead), lead_batch)
        await session.commit()

    min_lead_id_res = await session.execute(select(func.min(Lead.id)))
    min_lead_id = int(min_lead_id_res.scalar_one() or 1)

    # 6. Seed Activities (500,000 by default) in batches of 10,000
    batch_size_act = 10_000
    for start_idx in range(1, num_activities + 1, batch_size_act):
        end_idx = min(start_idx + batch_size_act, num_activities + 1)
        act_batch: list[dict[str, Any]] = []
        for i in range(start_idx, end_idx):
            act_batch.append(
                {
                    "lead_id": min_lead_id + (i % max(1, num_leads)),
                    "type": ACTIVITY_TYPES[i % len(ACTIVITY_TYPES)],
                    "message": ACTIVITY_MESSAGES[i % len(ACTIVITY_MESSAGES)],
                    "created_at": now - timedelta(seconds=i * 30),
                }
            )
        await session.execute(insert(Activity), act_batch)
        await session.commit()

    # 7. Seed sample LLMUsage records across the last 7 days for /admin/ai-costs
    llm_rows: list[dict[str, Any]] = []
    for i in range(1, 121):
        is_cached = (i % 3) == 0
        is_cheap = (i % 4) != 0
        model_name = "gpt-4o-mini" if is_cheap else "gpt-4o"
        feature_name = "ai_assistant" if (i % 2 == 0) else "smart_lead_capture"
        in_tok = 0 if is_cached else (180 + (i * 7) % 300)
        out_tok = 0 if is_cached else (95 + (i * 5) % 180)
        cost = (
            Decimal("0.000000")
            if is_cached
            else (Decimal("0.000420") if is_cheap else Decimal("0.004850"))
        )
        llm_rows.append(
            {
                "user_id": user_ids[i % len(user_ids)],
                "feature": feature_name,
                "model": model_name,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_usd": cost,
                "cache_hit": is_cached,
                "created_at": now - timedelta(hours=i * 1.2),
            }
        )
    await session.execute(insert(LLMUsage), llm_rows)
    await session.commit()

    # Refresh Materialized View if running on PostgreSQL
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        await session.execute(text("REFRESH MATERIALIZED VIEW monthly_kpis;"))
        await session.commit()

    elapsed_sec = round(time.perf_counter() - t0, 2)
    return {
        "customers": num_customers,
        "leads": num_leads,
        "activities": num_activities,
        "products": len(product_rows),
        "kb_docs": len(kb_docs),
        "llm_usage_rows": len(llm_rows),
        "elapsed_seconds": elapsed_sec,
    }


async def main() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    parser = argparse.ArgumentParser(description="Seed LeadPulse database with realistic CRM data.")
    parser.add_argument(
        "--seed-size",
        choices=["small", "full"],
        default=settings.seed_size,
        help="Preset dataset size: 'small' (10k customers, 30k leads, 60k activities for cloud free tier) or 'full' (10k customers, 200k leads, 500k activities)",
    )
    parser.add_argument("--customers", type=int, default=None, help="Number of customers (default: 10,000)")
    parser.add_argument(
        "--leads",
        type=int,
        default=None,
        help="Number of leads (default: 200,000 for full or 30,000 for small; supports up to 1,000,000)",
    )
    parser.add_argument(
        "--activities",
        type=int,
        default=None,
        help="Number of lead activities (default: 500,000 for full or 60,000 for small)",
    )
    args = parser.parse_args()

    is_small = args.seed_size == "small"
    customers_count = args.customers if args.customers is not None else 10_000
    leads_count = args.leads if args.leads is not None else (30_000 if is_small else 200_000)
    activities_count = (
        args.activities if args.activities is not None else (60_000 if is_small else 500_000)
    )

    if leads_count > 1_000_000:
        raise ValueError("--leads cannot exceed 1,000,000")

    print(
        f"[LeadPulse Seed] Starting bulk seed (mode={args.seed_size}): {customers_count:,} customers, "
        f"{leads_count:,} leads, {activities_count:,} activities..."
    )
    await ensure_tables_exist()
    async with AsyncSessionLocal() as session:
        summary = await seed_database(
            session,
            num_customers=customers_count,
            num_leads=leads_count,
            num_activities=activities_count,
        )
    print(f"[LeadPulse Seed] Completed in {summary['elapsed_seconds']}s -> {summary}")


if __name__ == "__main__":
    asyncio.run(main())
