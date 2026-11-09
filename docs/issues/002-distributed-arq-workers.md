# Issue #002: Migrate CPU-Heavy Background Jobs to Redis-Backed ARQ Workers

- **Status**: Deferred (Phase 2)
- **Labels**: `architecture`, `scalability`, `backend`
- **Related Tech Debt**: `TD-001`

## Context
`POST /api/v1/lab/cpu-heavy` currently offloads CPU work to a `ProcessPoolExecutor` and tracks job status in `_jobs_store` in memory.

## Acceptance Criteria
1. Persist job metadata (`job:{id}`) in Redis with a 24-hour TTL so any FastAPI replica can serve `GET /api/v1/lab/jobs/{id}`.
2. Move `_cpu_bound_report_worker` and the 15-minute `REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_kpis` cron job into a dedicated `arq` worker service in `docker-compose.yml`.
