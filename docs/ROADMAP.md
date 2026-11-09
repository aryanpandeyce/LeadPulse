# LeadPulse Product Roadmap & Scope Boundaries (Concept 9)

To ship a high-reliability, deployable CRM + AI Assistant on schedule without sacrificing engineering fundamentals, we explicitly separated **Phase 1 MVP (Must-Have)** from **Phase 2 (Nice-to-Have / Deferred)**.

---

## Non-Negotiables (Enforced Even in MVP Mode)
Regardless of shipping speed, the following guardrails were **never** compromised:
1. **Strict Input Validation**: Pydantic v2 schemas on every request and column whitelisting on every dynamic sort/filter (`CustomerRepository`).
2. **Parameterized Queries Only**: Zero SQL string concatenation anywhere in the codebase.
3. **Authentication & RBAC**: Bcrypt password hashing, short-lived JWT access tokens + refresh rotation, and `require_admin` protection on privileged operations.
4. **Unified Error Envelope & Correlation**: Every 4xx/5xx error returns `{ error: { code, message, status, request_id, details } }` with `X-Request-ID` in headers and structured JSON logs.
5. **Automated CI Quality Gates**: `ruff`, `mypy`, `pytest` (21 backend tests), and `vitest` running in GitHub Actions.
6. **Zero Hardcoded Secrets**: All credentials and model names injected via `.env` (`pydantic-settings`).

---

## Phase 1: MVP Scope (Shipped in Repository)
- [x] **10k Customers Directory (`/customers`)**: Server-side pagination, whitelisted sorting, `pg_trgm` GIN search, URL state sync, 300ms debounce, and streamed CSV export.
- [x] **200k+ Leads Activity Feed (`/leads`)**: Keyset cursor pagination on `(created_at DESC, id DESC)`, `selectinload` N+1 prevention, idempotent `POST /api/v1/leads`, and `/docs/pagination-benchmark`.
- [x] **Executive KPI Dashboard (`/dashboard`)**: Layered Redis Cache-Aside + PostgreSQL Materialized View (`monthly_kpis`) with concurrent refresh, stampede protection, and live source/latency badge.
- [x] **FastAPI Concurrency Lab (`/lab`)**: `asyncio.gather` vs event-loop blocking anti-pattern vs threadpool & `ProcessPoolExecutor` CPU job offloading + 50-request benchmark.
- [x] **Smart Lead Capture (`/smart-capture`)**: Pydantic JSON schema tool-use, defensive fence stripping, and 2-retry validation feedback loop.
- [x] **Cost-Controlled AI Assistant (`/ai-assistant` & `/admin/ai-costs`)**: Model routing, FAQ short-circuit, normalized Redis cache, RAG-lite top-3 chunk retrieval, Redis rate limiting, daily spend cap, and SSE streaming.
- [x] **Next.js `<Image>` Optimization (`/docs/image-demo`)**: Side-by-side 100-image benchmark with zero CLS and AVIF/WebP negotiation.

---

## Phase 2: Nice-to-Have / Next Iteration (Tracked in `docs/issues/`)
- [ ] **Semantic Vector Hybrid Search (`pgvector`)**: Combine `pg_trgm` keyword match with dense embedding cosine similarity (`docs/issues/001-pgvector-hybrid-rag.md`).
- [ ] **Distributed Celery / ARQ Worker Queue**: Move `ProcessPoolExecutor` in-memory job tracking to Redis-backed ARQ workers for multi-replica horizontal scaling (`docs/issues/002-distributed-arq-workers.md`).
- [ ] **HttpOnly Cookie Auth + CSRF Double-Submit**: Migrate browser JWT storage from `localStorage` to `HttpOnly; Secure; SameSite=Lax` cookies (`docs/issues/003-httponly-cookie-auth.md`).
