# Free-Tier Production Deployment Guide (`docs/DEPLOYMENT.md`)

LeadPulse is designed to deploy cleanly onto 100% free-tier cloud infrastructure for live portfolio demos:
- **Frontend (Next.js 14)** → **Vercel**
- **Backend (FastAPI + Docker)** → **Render** or **Railway**
- **PostgreSQL 16 (`pg_trgm`)** → **Neon** or **Supabase**
- **Redis** → **Upstash Serverless Redis**

---

## 1. Step-by-Step Deployment Order

### Step 1: Provision PostgreSQL on Neon (or Supabase)
1. Create a new project in [Neon](https://neon.tech) (PostgreSQL 16).
2. Copy the pooled/direct connection string and replace `postgresql://` with `postgresql+asyncpg://`:
   ```text
   postgresql+asyncpg://<user>:<password>@ep-cool-darkness-123456.us-east-2.aws.neon.tech/neondb?ssl=require
   ```
3. Neon supports `CREATE EXTENSION IF NOT EXISTS pg_trgm;` out of the box, which our Alembic migration (`0001_initial_schema.py`) runs automatically.

### Step 2: Provision Serverless Redis on Upstash
1. Create a free Redis database in [Upstash](https://upstash.com).
2. Copy the TLS Redis URL (`rediss://default:<password>@<endpoint>.upstash.io:6379`).

### Step 3: Deploy FastAPI Backend on Render (or Railway)
1. Connect your GitHub repo `https://github.com/aryanpandeyce/LeadPulse` to Render as a **Web Service**.
2. Set **Root Directory** to `backend` and **Runtime** to `Docker` (uses `backend/Dockerfile`).
3. Set the **Pre-Deploy / Start Command** to run Alembic migrations automatically before booting Uvicorn:
   ```bash
   sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
   ```
4. Seed a free-tier-friendly dataset (e.g. 10,000 customers, 50,000 leads, 100,000 activities so it fits well within Neon's 0.5 GB storage cap) using the Render Shell or locally pointed at your Neon `DATABASE_URL`:
   ```bash
   python -m app.scripts.seed --customers 10000 --leads 50000 --activities 100000
   ```

### Step 4: Deploy Next.js Frontend on Vercel
1. Import `https://github.com/aryanpandeyce/LeadPulse` into Vercel.
2. Set **Root Directory** to `frontend`.
3. Add environment variable `NEXT_PUBLIC_API_URL=https://<your-backend>.onrender.com/api/v1`.
4. Deploy. Once Vercel assigns your production domain (e.g. `https://leadpulse-crm.vercel.app`), update `CORS_ORIGINS` on Render to `["https://leadpulse-crm.vercel.app"]`.

---

## 2. Environment Variables Reference Table

### Backend (`backend/.env`)

| Variable | Example / Default | Required | Purpose |
| :--- | :--- | :---: | :--- |
| `ENVIRONMENT` | `production` | Yes | Sets environment mode (`development` \| `test` \| `production`) |
| `DATABASE_URL` | `postgresql+asyncpg://user:pw@host:5432/db` | Yes | Async SQLAlchemy + `asyncpg` connection URL |
| `REDIS_URL` | `rediss://default:pw@host.upstash.io:6379` | Yes | Upstash/Redis URL for KPI cache, prompt cache, and rate limits |
| `JWT_SECRET_KEY` | `<64-char-random-hex-secret>` | Yes | Signs 30-min access JWTs and 7-day refresh JWTs |
| `CORS_ORIGINS` | `["https://leadpulse.vercel.app"]` | Yes | Allowed browser origins; exposes `X-Request-ID` and `Retry-After` headers |
| `LLM_PROVIDER` | `openai` \| `anthropic` \| `mock` | Yes | Selects upstream LLM provider (`mock` works with zero API keys!) |
| `OPENAI_API_KEY` | `sk-...` | Optional | Required only when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Optional | Required only when `LLM_PROVIDER=anthropic` |
| `LLM_CHEAP_MODEL` | `gpt-4o-mini` | Yes | Model used by router for standard FAQ/extraction intents |
| `LLM_STRONG_MODEL` | `gpt-4o` | Yes | Model used by router for complex multi-factor reasoning |
| `LLM_DAILY_USER_BUDGET_USD` | `1.00` | Yes | Rolling 24-hour per-user AI spend cap |
| `LLM_RATE_LIMIT_PER_MINUTE` | `20` | Yes | Per-user AI requests/minute limit in Redis |
| `FEATURE_AI_STREAMING` | `true` | Yes | Feature flag toggling SSE streaming on `/ai-assistant` |
| `FEATURE_SMART_CAPTURE_RETRY` | `true` | Yes | Feature flag toggling 2-retry validation loop on `/smart-capture` |

### Frontend (`frontend/.env.local`)

| Variable | Example / Default | Required | Purpose |
| :--- | :--- | :---: | :--- |
| `NEXT_PUBLIC_API_URL` | `https://leadpulse-api.onrender.com/api/v1` | Yes | Base URL of the FastAPI backend |

---

## 3. Cross-Domain CORS & Auth Notes
- When hosting the frontend on `*.vercel.app` and the backend on `*.onrender.com`, browsers treat them as cross-site origins.
- Our FastAPI `CORSMiddleware` (`backend/app/main.py`) explicitly sets `allow_origins=settings.cors_origins`, `allow_headers=["*"]`, and `expose_headers=["X-Request-ID", "X-Response-Time-Ms", "Retry-After"]` so the typed frontend client (`frontend/src/lib/api-client.ts`) can read correlation IDs and `429 Retry-After` timers across domains.
