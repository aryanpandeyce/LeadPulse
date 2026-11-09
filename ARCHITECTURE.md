# LeadPulse System Architecture (`ARCHITECTURE.md` — Concept 10)

LeadPulse is designed as a **layered, testable, production-grade monorepo** where every layer has a single responsibility and zero business logic leaks into HTTP route handlers or UI components.

---

## 1. High-Level System Architecture Diagram

```mermaid
flowchart TB
    subgraph Browser["Next.js 14 App Router (TypeScript + Tailwind + TanStack Query)"]
        Pages["Pages: /customers, /leads, /dashboard,\n/smart-capture, /ai-assistant, /lab, /admin/ai-costs"]
        ApiClient["Typed API Client (api-client.ts)\nParses Unified Error Envelope + X-Request-ID"]
        Pages --> ApiClient
    end

    subgraph FastAPI["FastAPI Backend (Python 3.11+ Async)"]
        Middleware["RequestContextMiddleware\n(X-Request-ID + Security Headers + JSON Logs)\n+ Global Exception Handlers (errors.py)"]
        Routes["Thin Route Handlers (app/api/routes/*)\nInput validation & FastAPI Depends only"]
        Services["Service Layer (app/services/*)\nBusiness Logic, Caching, Rate Limits, Budgets"]
        Repos["Repository Layer (app/repositories/*)\nParameterized SQLAlchemy 2.0 Async Queries"]
        LlmLayer["LLM Layer (app/llm/*)\nRouter + Schema Tool-Use + Retry Loop"]

        Middleware --> Routes
        Routes --> Services
        Services --> Repos
        Services --> LlmLayer
    end

    subgraph DataStores["Data & Cache Infrastructure"]
        Postgres[("PostgreSQL 16 + pg_trgm\n10k customers, 200k leads, 500k activities\n+ monthly_kpis Materialized View")]
        Redis[("Redis 7\nKPI Cache-Aside + Prompt Cache\n+ Per-User Rate Limiter")]
        Providers["External LLM APIs\n(OpenAI / Anthropic / Deterministic Mock)"]
    end

    ApiClient -->|REST / SSE JSON| Middleware
    Repos -->|asyncpg Pool| Postgres
    Services -->|redis.asyncio| Redis
    LlmLayer -->|httpx.AsyncClient| Providers
```

---

## 2. Backend Layered Responsibility Rules

| Layer | Directory | Allowed Responsibilities | Forbidden in This Layer |
| :--- | :--- | :--- | :--- |
| **API Routes** | `backend/app/api/routes/` | Parse query/body via Pydantic, resolve `Depends(get_db_session)` / `Depends(get_current_user)`, call a Service method, return typed schema. | Raw SQL/ORM queries, Redis calls, business branching, `try/except HTTPException` boilerplate. |
| **Services** | `backend/app/services/` | Domain logic, cache-aside orchestration, rate-limit/budget checks, calling repositories and LLM client. | HTTP status codes, raw `Request`/`Response` manipulation, unparameterized SQL. |
| **Repositories** | `backend/app/repositories/` | Parameterized SQLAlchemy 2.0 queries, column whitelisting, cursor encoding/decoding, `selectinload` eager loading. | HTTP exceptions, business policy decisions. |
| **LLM Module** | `backend/app/llm/` | Provider abstraction (`OpenAI`, `Anthropic`, `mock`), `ExtractedLead` JSON schema generation, fence stripping, validation retry loop, model routing. | Direct database mutations. |
| **Core** | `backend/app/core/` | `Settings` (`.env`), `AppError` hierarchy & global handlers, `X-Request-ID` middleware, structured JSON logging, JWT + bcrypt security. | Feature-specific logic. |

---

## 3. Request Lifecycle & Error Correlation Flow

```mermaid
sequenceDiagram
    participant UI as Next.js Client
    participant MW as RequestContextMiddleware
    participant Route as FastAPI Route
    participant Svc as Service Layer
    participant Handler as Global Exception Handler

    UI->>MW: GET /api/v1/customers?sort_by=bad_col
    MW->>MW: Generate UUID -> request_id_ctx_var
    MW->>Route: Forward Request
    Route->>Svc: get_customers_page(sort_by="bad_col")
    Svc-->>Handler: Raise ValidationError("INVALID_SORT_COLUMN", 400)
    Handler->>Handler: Log structured JSON with request_id
    Handler-->>UI: HTTP 400 { error: { code, message, status, request_id, details } } + Header X-Request-ID
    UI->>UI: ApiClientError parsed -> Toast displays message + request_id
```

