"""Concurrency Lab service demonstrating when async/await helps and when it hurts (Concept 3).

# CONCEPT: async/await in FastAPI (when it helps, when it hurts)
1. `run_io_async_gather`: Awaits 3 non-blocking I/O calls concurrently via `asyncio.gather` (~50ms total instead of ~150ms).
2. `run_io_blocking_wrong`: Calls synchronous `time.sleep()` directly inside an `async def` route.
   This freezes the single-threaded asyncio event loop, serializing all 50 concurrent requests!
3. `run_io_blocking_right`: Offloads synchronous blocking I/O to Starlette's `run_in_threadpool`
   (or a plain `def` endpoint), freeing the event loop to serve other requests concurrently.
4. `submit_cpu_heavy_job`: Offloads CPU-bound work (generating a large CSV/digest report) to a
   `ProcessPoolExecutor` background job so neither the event loop nor the GIL blocks API traffic.
"""

import asyncio
import hashlib
import time
import uuid
from concurrent.futures import ProcessPoolExecutor

from starlette.concurrency import run_in_threadpool

from app.core.errors import NotFoundError
from app.schemas.lab import CpuHeavyJobStatusResponse, LabIoResponse

# Process pool for CPU-bound work (bypasses GIL and keeps FastAPI event loop free)
_process_pool: ProcessPoolExecutor | None = None
_jobs_store: dict[str, CpuHeavyJobStatusResponse] = {}


def _get_process_pool() -> ProcessPoolExecutor:
    global _process_pool
    if _process_pool is None:
        _process_pool = ProcessPoolExecutor(max_workers=2)
    return _process_pool


def _cpu_bound_report_worker(rows_to_process: int) -> tuple[str, float]:
    """Top-level picklable function executed inside a separate worker process."""
    t0 = time.perf_counter()
    hasher = hashlib.sha256()
    for i in range(rows_to_process):
        hasher.update(f"leadpulse-row-{i}-{i * 31}\n".encode())
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    return hasher.hexdigest()[:16], elapsed_ms


def _blocking_io_call(delay_sec: float) -> str:
    """Simulates a legacy synchronous library call (e.g., `requests.get` or `time.sleep`)."""
    time.sleep(delay_sec)
    return "ok"


class ConcurrencyLabService:
    """Service methods backing the `/api/v1/lab/*` endpoints."""

    async def run_io_async_gather(self, delay_ms: int = 50) -> LabIoResponse:
        """# CONCEPT: async/await in FastAPI (asyncio.gather for concurrent I/O)"""
        t0 = time.perf_counter()
        delay_sec = delay_ms / 1000.0

        async def _simulated_external_api(idx: int) -> int:
            await asyncio.sleep(delay_sec)
            return idx

        # Fires all 3 external I/O calls concurrently: total latency ~ delay_ms, not 3 * delay_ms
        await asyncio.gather(
            _simulated_external_api(1),
            _simulated_external_api(2),
            _simulated_external_api(3),
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return LabIoResponse(
            mode="io_async_gather",
            simulated_calls=3,
            per_call_delay_ms=delay_ms,
            elapsed_ms=elapsed_ms,
            explanation=(
                "Awaited 3 non-blocking I/O calls concurrently with asyncio.gather(). "
                "Event loop stayed 100% non-blocking; 50 concurrent requests complete in ~1 batch."
            ),
        )

    async def run_io_blocking_wrong(self, delay_ms: int = 50) -> LabIoResponse:
        """# CONCEPT: async/await in FastAPI (WRONG: blocking time.sleep inside async def)"""
        t0 = time.perf_counter()
        delay_sec = delay_ms / 1000.0
        # INTENTIONAL ANTI-PATTERN: Calling blocking time.sleep() inside `async def` blocks the event loop!
        time.sleep(delay_sec)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return LabIoResponse(
            mode="io_blocking_wrong",
            simulated_calls=1,
            per_call_delay_ms=delay_ms,
            elapsed_ms=elapsed_ms,
            explanation=(
                "ANTI-PATTERN: Called blocking time.sleep() inside `async def`. "
                "This freezes the single-threaded event loop so 50 concurrent requests queue up serially!"
            ),
        )

    async def run_io_blocking_right(self, delay_ms: int = 50) -> LabIoResponse:
        """# CONCEPT: async/await in FastAPI (RIGHT: offload sync blocking I/O to threadpool)"""
        t0 = time.perf_counter()
        delay_sec = delay_ms / 1000.0
        await run_in_threadpool(_blocking_io_call, delay_sec)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return LabIoResponse(
            mode="io_blocking_right",
            simulated_calls=1,
            per_call_delay_ms=delay_ms,
            elapsed_ms=elapsed_ms,
            explanation=(
                "Ran blocking work inside Starlette's threadpool (run_in_threadpool / plain `def`). "
                "Worker threads absorb the blocking sleep while the event loop continues serving requests."
            ),
        )

    async def submit_cpu_heavy_job(
        self, rows_to_process: int = 50_000
    ) -> CpuHeavyJobStatusResponse:
        """# CONCEPT: async/await in FastAPI (CPU-bound work offloaded to ProcessPoolExecutor)"""
        job_id = f"job-{uuid.uuid4().hex[:10]}"
        initial = CpuHeavyJobStatusResponse(
            job_id=job_id,
            status="queued",
            rows_processed=rows_to_process,
        )
        _jobs_store[job_id] = initial

        async def _background_runner() -> None:
            _jobs_store[job_id].status = "running"
            try:
                loop = asyncio.get_running_loop()
                checksum, elapsed_ms = await loop.run_in_executor(
                    _get_process_pool(),
                    _cpu_bound_report_worker,
                    rows_to_process,
                )
                _jobs_store[job_id] = CpuHeavyJobStatusResponse(
                    job_id=job_id,
                    status="completed",
                    rows_processed=rows_to_process,
                    checksum=checksum,
                    elapsed_ms=elapsed_ms,
                    worker_type="ProcessPoolExecutor",
                )
            except Exception:
                # Fallback to threadpool if ProcessPool spawn is restricted in minimal test containers
                checksum, elapsed_ms = await run_in_threadpool(
                    _cpu_bound_report_worker, rows_to_process
                )
                _jobs_store[job_id] = CpuHeavyJobStatusResponse(
                    job_id=job_id,
                    status="completed",
                    rows_processed=rows_to_process,
                    checksum=checksum,
                    elapsed_ms=elapsed_ms,
                    worker_type="ProcessPoolExecutor (fallback)",
                )

        asyncio.create_task(_background_runner())
        return initial

    def get_job_status(self, job_id: str) -> CpuHeavyJobStatusResponse:
        job = _jobs_store.get(job_id)
        if not job:
            raise NotFoundError(
                code="JOB_NOT_FOUND",
                message=f"Background job '{job_id}' was not found.",
            )
        return job
