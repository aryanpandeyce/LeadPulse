# Conscious Technical Debt Register (`TECH_DEBT.md` — Concept 9)

Senior engineers take **deliberate, bounded shortcuts** to validate product value quickly, while documenting each shortcut with its blast radius, effort to remediate, and trigger condition for paying it down.

---

## Ticket TD-001: In-Process `ProcessPoolExecutor` Job Store for CPU-Heavy Reports
- **Location**: `backend/app/services/lab_service.py` (`_jobs_store` dictionary + `ProcessPoolExecutor`)
- **Shortcut Taken**: Stored background job status (`queued | running | completed`) in a process-local Python dictionary instead of an external broker (Celery / ARQ / Redis).
- **Why We Took It**: Kept local `docker compose up` and free-tier deployment simple (no separate worker container required for the portfolio demo).
- **Impact / Risk**: If the FastAPI container runs with multiple `--workers` or scales horizontally across 2+ instances, `GET /api/v1/lab/jobs/{id}` could land on a replica that doesn't hold `_jobs_store[job_id]` in memory.
- **Effort to Fix**: **S (3 hours)** — store job state JSON in Redis (`job:{id}`) and run `arq` worker against the existing Redis instance.
- **When to Fix**: Before scaling backend replicas beyond `1` in production (`docs/issues/002-distributed-arq-workers.md`).

---

## Ticket TD-002: Keyword/ILIKE RAG-Lite Instead of Hybrid `pgvector` Embeddings
- **Location**: `backend/app/services/ai_service.py` (`retrieve_rag_chunks`)
- **Shortcut Taken**: Retrieved top-3 knowledge base chunks via keyword matching on `knowledge_base_docs` instead of generating OpenAI/Voyage vector embeddings on every query.
- **Why We Took It**: Zero external embedding API latency/cost and 100% deterministic offline operation for reviewers cloning the repo without API keys.
- **Impact / Risk**: Synonym queries that share zero keywords with a document (e.g., "how much does the tool cost?" vs "pricing") rely on our `keywords` column metadata rather than semantic vector similarity.
- **Effort to Fix**: **M (1 day)** — add `embedding vector(1536)` column (our `pgvector/pgvector:pg16` Docker image already includes the extension!) and run Reciprocal Rank Fusion (RRF) over `pgvector` + `tsvector`.
- **When to Fix**: When the knowledge base grows beyond 100 documents (`docs/issues/001-pgvector-hybrid-rag.md`).

---

## Ticket TD-003: Process-Local Stampede Lock + Redis Version Key
- **Location**: `backend/app/services/kpi_service.py` (`_local_stampede_lock`)
- **Shortcut Taken**: Used an `asyncio.Lock()` per FastAPI worker process to coalesce concurrent cache misses on `/api/v1/kpis`.
- **Why We Took It**: Eliminates 98%+ of stampede queries with 3 lines of standard library code and zero distributed lock deadlocks.
- **Impact / Risk**: With $W$ worker processes, a cold cache miss under heavy load could allow at most $W$ queries (e.g. 4 queries instead of 1) to hit the `monthly_kpis` Materialized View simultaneously. Because `monthly_kpis` is already pre-aggregated (~60 rows, ~2ms), 4 concurrent reads are harmless at current scale.
- **Effort to Fix**: **S (2 hours)** — use Redis `SET lock:kpis:rebuild 1 NX EX 10` with pub/sub wakeup.
- **When to Fix**: When running >8 backend worker replicas or if the underlying fallback query takes >100ms.

---

## Ticket TD-004: Browser JWT Storage in `localStorage` for Cross-Origin Free-Tier Demo
- **Location**: `frontend/src/lib/api-client.ts`
- **Shortcut Taken**: Stored demo JWT tokens in `localStorage` and attached via `Authorization: Bearer <token>`.
- **Why We Took It**: Free-tier deployments host the frontend on `*.vercel.app` and the backend on `*.onrender.com` (different top-level domains where third-party cookies are blocked by Safari ITP and Chrome).
- **Impact / Risk**: `localStorage` is readable by JavaScript if an XSS vulnerability were ever introduced.
- **Effort to Fix**: **S (4 hours)** — put both apps behind a custom domain (`app.leadpulse.io` + `api.leadpulse.io`) and switch to `HttpOnly; Secure; SameSite=Lax` cookies (`docs/issues/003-httponly-cookie-auth.md`).
- **When to Fix**: Immediately upon binding a custom production domain.
