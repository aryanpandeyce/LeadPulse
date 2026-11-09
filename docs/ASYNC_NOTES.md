# `async/await` in FastAPI: When It Helps, When It Hurts (Concept 3)

## 1. Executive Summary
FastAPI runs on an **event loop** (`uvloop` / `asyncio`) inside a single OS thread per worker process.
- **When `async def` helps**: Non-blocking **I/O-bound work** (`asyncpg` PostgreSQL queries, `redis.asyncio`, `httpx.AsyncClient` LLM calls). While Request A awaits network bytes from Postgres or OpenAI, the event loop immediately switches to serve Requests B..Z. Furthermore, multiple independent I/O calls inside a single request can run in parallel via `asyncio.gather()`.
- **When `async def` hurts (The Sync-in-Async Pitfall)**: Calling blocking synchronous I/O (`time.sleep`, `requests.get`, `boto3`, synchronous `psycopg2`) inside an `async def` route **freezes the entire event loop thread**. Even `/health` probes stall until the blocking call returns!
- **When `async def` doesn't speed up work (CPU-bound tasks)**: Heavy Python loops, large CSV/PDF generation, or cryptographic hashing hold the Python GIL and starve the event loop. These must be offloaded to a `ProcessPoolExecutor` or background task queue.

---

## 2. Benchmark Results: 50 Concurrent Requests (`50ms` simulated I/O delay)

> **Measured on**: Windows 10 (AMD64) / Python 3.10.6 + FastAPI / PostgreSQL 16.15 / 2026-11-10  
> Raw output saved in [`docs/benchmarks/benchmark_async.txt`](benchmarks/benchmark_async.txt).

| Endpoint Strategy | What It Does | Total Wall Time (50 reqs) | p50 Latency | p95 Latency |
| :--- | :--- | ---: | ---: | ---: |
| **`GET /api/v1/lab/io-async`** | Awaits 3 non-blocking calls via `asyncio.gather()` | **`193.7 ms`** | `144.5 ms` | `187.1 ms` |
| **`GET /api/v1/lab/io-blocking-right`** | Offloads blocking sleep to `run_in_threadpool` (40 worker threads) | **`186.1 ms`** | `122.8 ms` | `143.6 ms` |
| **`GET /api/v1/lab/io-blocking-wrong`** | **WRONG**: Calls `time.sleep(0.05)` inside `async def` | **`3,179.7 ms`** | `3,149.7 ms` | `3,161.2 ms` |

> **Key Takeaway for Interviews**: Putting a `50ms` blocking call inside `async def` spiked total wall time by **16.4x** (`193.7 ms` → `3,179.7 ms`) and p95 latency from `187.1 ms` to **`3,161.2 ms`** because all 50 requests executed strictly one-by-one on the blocked event loop.

---

## 3. Decision Matrix for FastAPI Endpoints

| Workload Type | Example in LeadPulse | How to Implement in FastAPI | Why |
| :--- | :--- | :--- | :--- |
| **Async I/O** | `asyncpg` DB queries, `redis.asyncio`, `httpx.AsyncClient` LLM calls | `async def` + `await` (and `asyncio.gather` when independent) | Zero thread overhead; scales to thousands of concurrent connections per worker |
| **Legacy Blocking I/O** | Synchronous third-party SDK (`requests`, `urllib`, sync file I/O) | Plain `def` route OR `await run_in_threadpool(fn, ...)` | FastAPI automatically runs plain `def` endpoints in an external threadpool so the event loop never blocks |
| **CPU-Bound** | Generating a 50,000-row digest report (`POST /api/v1/lab/cpu-heavy`) | `ProcessPoolExecutor` / Celery / ARQ background worker + `202 Accepted` job polling (`GET /lab/jobs/{id}`) | Bypasses the Python GIL across multiple CPU cores and keeps API latency < 5ms |

