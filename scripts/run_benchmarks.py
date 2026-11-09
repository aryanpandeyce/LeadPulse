"""Reproducible PostgreSQL 16 + Redis 7 benchmark suite for LeadPulse (Step A4).

Seeds 10,000 customers, 200,000 leads, and 500,000 activities into PostgreSQL (if not already seeded),
runs EXPLAIN (ANALYZE, BUFFERS) and endpoint latency benchmarks, and writes raw outputs to `docs/benchmarks/*.txt`.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.redis import close_redis  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories.lead_repository import LeadRepository  # noqa: E402
from app.scripts.seed import ensure_tables_exist, seed_database  # noqa: E402

BENCH_DIR = ROOT_DIR / "docs" / "benchmarks"


async def main() -> None:
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    await ensure_tables_exist()

    async with AsyncSessionLocal() as session:
        ver_res = await session.execute(text("SELECT version()"))
        pg_version = str(ver_res.scalar_one())
        print(f"[Benchmark] Connected to: {pg_version}")

        lead_cnt_res = await session.execute(text("SELECT COUNT(*) FROM leads"))
        lead_cnt = int(lead_cnt_res.scalar_one() or 0)
        if lead_cnt < 200_000:
            print(f"[Benchmark] Seeding 10k customers, 200k leads, 500k activities (current leads={lead_cnt})...")
            seed_summary = await seed_database(
                session,
                num_customers=10_000,
                num_leads=200_000,
                num_activities=500_000,
                reset=True,
            )
            print(f"[Benchmark] Seed completed: {seed_summary}")
        else:
            print(f"[Benchmark] Database already has {lead_cnt:,} leads.")

        await session.execute(text("ANALYZE customers;"))
        await session.execute(text("ANALYZE leads;"))
        await session.execute(text("ANALYZE activities;"))
        await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_kpis;"))
        await session.commit()

        measured_header = (
            f"Measured on: {platform.system()} {platform.release()} ({platform.machine()}) / "
            f"{pg_version.split(',')[0]} / 10,000 customers, 200,000 leads, 500,000 activities / "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
            + "=" * 95
            + "\n\n"
        )

        # 1. EXPLAIN ANALYZE on customers trigram search (Seq Scan vs Bitmap Index Scan on ix_customers_name_email_trgm)
        await session.execute(text("SET enable_indexscan = off;"))
        await session.execute(text("SET enable_bitmapscan = off;"))
        seq_res = await session.execute(
            text(
                "EXPLAIN (ANALYZE, BUFFERS) "
                "SELECT id, name, email, city, status, total_purchase_amount "
                "FROM customers "
                "WHERE (name || ' ' || email) ILIKE '%aryan%' "
                "ORDER BY total_purchase_amount DESC LIMIT 25;"
            )
        )
        seq_plan = "\n".join(row[0] for row in seq_res)

        await session.execute(text("SET enable_indexscan = on;"))
        await session.execute(text("SET enable_bitmapscan = on;"))
        idx_res = await session.execute(
            text(
                "EXPLAIN (ANALYZE, BUFFERS) "
                "SELECT id, name, email, city, status, total_purchase_amount "
                "FROM customers "
                "WHERE (name || ' ' || email) ILIKE '%aryan%' "
                "ORDER BY total_purchase_amount DESC LIMIT 25;"
            )
        )
        idx_plan = "\n".join(row[0] for row in idx_res)

        trgm_txt = (
            measured_header
            + "--- BEFORE INDEX (Seq Scan with enable_indexscan=off, enable_bitmapscan=off) ---\n"
            + seq_plan
            + "\n\n--- AFTER INDEX (Bitmap Index Scan using ix_customers_name_email_trgm) ---\n"
            + idx_plan
            + "\n"
        )
        (BENCH_DIR / "explain_analyze_customers_trgm.txt").write_text(trgm_txt, encoding="utf-8")
        print("[Benchmark] Saved docs/benchmarks/explain_analyze_customers_trgm.txt")

        # 2. EXPLAIN ANALYZE on leads: OFFSET 150,000 vs Keyset WHERE (created_at, id) < (:ts, :id)
        offset_explain_res = await session.execute(
            text(
                "EXPLAIN (ANALYZE, BUFFERS) "
                "SELECT id, customer_id, name, email, source, status, revenue, owner_id, created_at "
                "FROM leads ORDER BY created_at DESC, id DESC OFFSET 150000 LIMIT 50;"
            )
        )
        offset_plan = "\n".join(row[0] for row in offset_explain_res)

        anchor_res = await session.execute(
            text(
                "SELECT created_at, id FROM leads ORDER BY created_at DESC, id DESC OFFSET 150000 LIMIT 1;"
            )
        )
        anchor_row = anchor_res.first()
        assert anchor_row is not None
        anchor_dt, anchor_id = anchor_row[0], int(anchor_row[1])

        keyset_explain_res = await session.execute(
            text(
                "EXPLAIN (ANALYZE, BUFFERS) "
                "SELECT id, customer_id, name, email, source, status, revenue, owner_id, created_at "
                "FROM leads "
                "WHERE (created_at, id) < (:cursor_dt, :cursor_id) "
                "ORDER BY created_at DESC, id DESC LIMIT 50;"
            ),
            {"cursor_dt": anchor_dt, "cursor_id": anchor_id},
        )
        keyset_plan = "\n".join(row[0] for row in keyset_explain_res)

        keyset_txt = (
            measured_header
            + "--- OFFSET PAGINATION AT DEPTH 150,000 (OFFSET 150000 LIMIT 50) ---\n"
            + offset_plan
            + "\n\n--- KEYSET CURSOR PAGINATION AT DEPTH 150,000 (WHERE (created_at, id) < (:ts, :id) LIMIT 50) ---\n"
            + keyset_plan
            + "\n"
        )
        (BENCH_DIR / "explain_analyze_leads_keyset.txt").write_text(keyset_txt, encoding="utf-8")
        print("[Benchmark] Saved docs/benchmarks/explain_analyze_leads_keyset.txt")

        # 3. Pagination latency table across depths
        repo = LeadRepository(session)
        depths = [100, 1_000, 10_000, 50_000, 100_000, 150_000]
        pag_lines = [
            measured_header,
            f"{'Depth (Rows)':<15} | {'OFFSET Latency (ms)':<22} | {'Keyset Cursor (ms)':<20} | {'Speedup':<10}",
            "-" * 78,
        ]
        for depth in depths:
            cur_token = await repo.get_anchor_cursor_for_offset(depth)
            page_num = (depth // 50) + 1

            # Measure average of 3 runs for stability
            off_times = []
            key_times = []
            for _ in range(3):
                t0 = time.perf_counter()
                await repo.list_offset(page=page_num, limit=50, include_activities=False)
                off_times.append((time.perf_counter() - t0) * 1000)

                t1 = time.perf_counter()
                await repo.list_keyset(cursor=cur_token, limit=50, include_activities=False)
                key_times.append((time.perf_counter() - t1) * 1000)

            off_ms = round(statistics.mean(off_times), 2)
            key_ms = round(statistics.mean(key_times), 2)
            speedup = round(off_ms / max(key_ms, 0.05), 1)
            pag_lines.append(
                f"{depth:<15,d} | {off_ms:<22.2f} | {key_ms:<20.2f} | {speedup}x"
            )

        (BENCH_DIR / "benchmark_pagination.txt").write_text(
            "\n".join(pag_lines) + "\n", encoding="utf-8"
        )
        print("[Benchmark] Saved docs/benchmarks/benchmark_pagination.txt")

    # 4. KPI 3-layer latency benchmark (Raw vs Materialized View vs Redis)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Warm up + ensure Redis cache is populated
        await client.get("/api/v1/kpis")

        raw_times = []
        mv_times = []
        redis_times = []
        for _ in range(5):
            r_raw = await client.get("/api/v1/kpis/raw")
            raw_times.append(float(r_raw.json()["query_ms"]))

            r_mv = await client.get("/api/v1/kpis?bypass_redis=true")
            mv_times.append(float(r_mv.json()["query_ms"]))

        # Populate Redis once more and measure 5 Redis hits
        await client.get("/api/v1/kpis")
        for _ in range(5):
            r_red = await client.get("/api/v1/kpis")
            redis_times.append(float(r_red.json()["query_ms"]))

        kpi_txt = (
            measured_header
            + "KPI Endpoint 3-Tier Latency Comparison (5-run mean on 200,000 leads):\n"
            + "-" * 78 + "\n"
            + f"1. Raw SQL GROUP BY scan (`GET /api/v1/kpis/raw`)                 : {statistics.mean(raw_times):.2f} ms\n"
            + f"2. PostgreSQL Materialized View (`GET /api/v1/kpis?bypass_redis=true`) : {statistics.mean(mv_times):.2f} ms\n"
            + f"3. Redis Cache Hit (`GET /api/v1/kpis`)                           : {statistics.mean(redis_times):.2f} ms\n"
        )
        (BENCH_DIR / "benchmark_kpis.txt").write_text(kpi_txt, encoding="utf-8")
        print("[Benchmark] Saved docs/benchmarks/benchmark_kpis.txt")

        # 5. Async Concurrency Lab benchmark (50 concurrent requests)
        endpoints = [
            ("1. io-async (asyncio.gather)", "/api/v1/lab/io-async?delay_ms=50"),
            ("2. io-blocking-wrong (time.sleep in async def)", "/api/v1/lab/io-blocking-wrong?delay_ms=50"),
            ("3. io-blocking-right (run_in_threadpool)", "/api/v1/lab/io-blocking-right?delay_ms=50"),
        ]
        async_lines = [
            measured_header,
            "FastAPI Concurrency Benchmark (50 concurrent requests, delay_ms=50):",
            "-" * 92,
            f"{'Mode':<46} | {'Total Wall (ms)':<15} | {'p50 (ms)':<10} | {'p95 (ms)':<10}",
            "-" * 92,
        ]
        for label, url in endpoints:
            t_start = time.perf_counter()

            async def _one_req(target_url: str) -> float:
                r0 = time.perf_counter()
                resp = await client.get(target_url)
                assert resp.status_code == 200
                return (time.perf_counter() - r0) * 1000

            latencies = sorted(await asyncio.gather(*[_one_req(url) for _ in range(50)]))
            total_wall = round((time.perf_counter() - t_start) * 1000, 1)
            p50 = round(statistics.median(latencies), 1)
            p95 = round(latencies[int(0.95 * len(latencies)) - 1], 1)
            async_lines.append(
                f"{label:<46} | {total_wall:<15.1f} | {p50:<10.1f} | {p95:<10.1f}"
            )

        (BENCH_DIR / "benchmark_async.txt").write_text(
            "\n".join(async_lines) + "\n", encoding="utf-8"
        )
        print("[Benchmark] Saved docs/benchmarks/benchmark_async.txt")

    await close_redis()
    await engine.dispose()
    print("[Benchmark] ALL BENCHMARKS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
