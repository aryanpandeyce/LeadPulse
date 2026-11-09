"""Benchmark script firing 50 concurrent requests at each Concurrency Lab endpoint (Concept 3).

Usage:
    python -m app.scripts.benchmark_async
"""

import asyncio
import statistics
import time

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _benchmark_endpoint(
    client: AsyncClient,
    name: str,
    path: str,
    concurrency: int = 50,
    delay_ms: int = 40,
) -> dict[str, float | str]:
    latencies: list[float] = []

    async def _one_call() -> None:
        t0 = time.perf_counter()
        resp = await client.get(f"{path}?delay_ms={delay_ms}")
        assert resp.status_code == 200
        latencies.append((time.perf_counter() - t0) * 1000)

    wall_start = time.perf_counter()
    await asyncio.gather(*[_one_call() for _ in range(concurrency)])
    wall_total_ms = round((time.perf_counter() - wall_start) * 1000, 2)

    latencies.sort()
    p50 = round(statistics.median(latencies), 2)
    p95 = round(latencies[int(len(latencies) * 0.95) - 1], 2)
    rps = round((concurrency / (wall_total_ms / 1000.0)), 1)
    return {
        "name": name,
        "wall_ms": wall_total_ms,
        "p50_ms": p50,
        "p95_ms": p95,
        "rps": rps,
    }


async def main() -> None:
    concurrency = 50
    delay_ms = 40
    print("=" * 86)
    print(
        f"LEADPULSE ASYNC CONCURRENCY BENCHMARK ({concurrency} Concurrent Requests, {delay_ms}ms I/O Delay)"
    )
    print("=" * 86)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r_async = await _benchmark_endpoint(
            client,
            "1. /lab/io-async (asyncio.gather, 3x I/O)",
            "/api/v1/lab/io-async",
            concurrency=concurrency,
            delay_ms=delay_ms,
        )
        r_right = await _benchmark_endpoint(
            client,
            "2. /lab/io-blocking-right (run_in_threadpool)",
            "/api/v1/lab/io-blocking-right",
            concurrency=concurrency,
            delay_ms=delay_ms,
        )
        r_wrong = await _benchmark_endpoint(
            client,
            "3. /lab/io-blocking-wrong (time.sleep in async)",
            "/api/v1/lab/io-blocking-wrong",
            concurrency=concurrency,
            delay_ms=delay_ms,
        )

    print(
        f"{'Endpoint Strategy':<46} | {'Wall Total':>10} | {'p50 (ms)':>9} | {'p95 (ms)':>9} | {'Throughput':>10}"
    )
    print("-" * 86)
    for row in (r_async, r_right, r_wrong):
        print(
            f"{str(row['name']):<46} | {row['wall_ms']:>8}ms | {row['p50_ms']:>7}ms | {row['p95_ms']:>7}ms | {row['rps']:>7} req/s"
        )
    print("=" * 86)


if __name__ == "__main__":
    asyncio.run(main())
