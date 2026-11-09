"""CLI Benchmark script comparing Offset/Limit vs Keyset (Cursor) pagination at pages 1, 100, 1000, and 4000.

Usage:
    python -m app.scripts.benchmark_pagination
"""

import asyncio

from app.core.database import AsyncSessionLocal
from app.services.lead_service import LeadService


async def main() -> None:
    print("=" * 78)
    print("LEADPULSE PAGINATION BENCHMARK: OFFSET/LIMIT vs KEYSET (CURSOR) ON LEADS")
    print("=" * 78)
    async with AsyncSessionLocal() as session:
        service = LeadService(session)
        report = await service.run_pagination_benchmark(pages=[1, 100, 1000, 4000], limit=50)

    print(f"Total Leads in DB : {report.total_leads_in_db:,}")
    print(f"Page Size (limit) : {report.limit_per_page}")
    print("-" * 78)
    print(f"{'Page':>8} | {'OFFSET Rows':>14} | {'OFFSET (ms)':>14} | {'Keyset (ms)':>14} | {'Speedup':>10}")
    print("-" * 78)
    for pt in report.results:
        print(
            f"{pt.page:>8} | {pt.offset_rows:>14,} | {pt.offset_ms:>14.3f} | {pt.keyset_ms:>14.3f} | {pt.speedup_factor:>9.2f}x"
        )
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
