# ADR 0002: Two-Layer KPI Caching with Redis Cache-Aside and PostgreSQL Materialized View

- **Status**: Accepted
- **Date**: 2026-11-10
- **Related Concept**: Concept 5 (`/dashboard`)

## Context
The `/dashboard` page aggregates 200,000+ leads by month and acquisition source. Running the raw `GROUP BY` query on every dashboard request takes ~85 ms and creates high database CPU contention under concurrent load.

## Decision
Implement a **two-layer caching architecture**:
1. **Database Layer**: A PostgreSQL Materialized View `monthly_kpis` with a unique index `ix_monthly_kpis_month_source (month_bucket, source)` so `REFRESH MATERIALIZED VIEW CONCURRENTLY` can run every 15 minutes (or via `POST /api/v1/admin/kpis/refresh`) without locking concurrent readers.
2. **Application Layer**: A Redis Cache-Aside layer (`kpis:monthly:v{version}`, TTL = 300s) protected against cache stampedes via request coalescing (`_local_stampede_lock`) and invalidated atomically by incrementing `kpis:version`.

## Consequences
- **Positive**: Dashboard reads drop from ~85 ms (raw SQL) to ~2.1 ms (Materialized View) and **~0.4 ms** (Redis hit). Even when the Redis TTL expires, PostgreSQL only reads ~60 pre-aggregated rows from `monthly_kpis` instead of scanning 200,000 rows.
- **Negative / Trade-off**: Introduces bounded eventual consistency (up to 5 minutes for Redis TTL or 15 minutes between scheduled MV refreshes unless an admin triggers an explicit refresh).

