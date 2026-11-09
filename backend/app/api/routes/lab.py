"""Thin API routes for Concept 3: FastAPI Concurrency Lab (/lab/io-async, /lab/io-blocking-wrong, /lab/io-blocking-right, /lab/cpu-heavy)."""

from fastapi import APIRouter, Query

from app.schemas.lab import (
    CpuHeavyJobCreateRequest,
    CpuHeavyJobStatusResponse,
    LabIoResponse,
)
from app.services.lab_service import ConcurrencyLabService

router = APIRouter(prefix="/lab", tags=["Concurrency Lab (Concept 3: async/await)"])


@router.get(
    "/io-async",
    response_model=LabIoResponse,
    summary="Await 3 simulated external API calls concurrently with asyncio.gather",
)
async def lab_io_async(
    delay_ms: int = Query(default=50, ge=5, le=500),
) -> LabIoResponse:
    """# CONCEPT: async/await in FastAPI (Non-blocking I/O with asyncio.gather)"""
    service = ConcurrencyLabService()
    return await service.run_io_async_gather(delay_ms=delay_ms)


@router.get(
    "/io-blocking-wrong",
    response_model=LabIoResponse,
    summary="WRONG WAY: Calls blocking time.sleep inside async def, freezing the event loop",
)
async def lab_io_blocking_wrong(
    delay_ms: int = Query(default=50, ge=5, le=500),
) -> LabIoResponse:
    """# CONCEPT: async/await in FastAPI (Event loop blocking anti-pattern)"""
    service = ConcurrencyLabService()
    return await service.run_io_blocking_wrong(delay_ms=delay_ms)


@router.get(
    "/io-blocking-right",
    response_model=LabIoResponse,
    summary="RIGHT WAY: Offloads blocking I/O to threadpool so the event loop stays responsive",
)
async def lab_io_blocking_right(
    delay_ms: int = Query(default=50, ge=5, le=500),
) -> LabIoResponse:
    """# CONCEPT: async/await in FastAPI (Sync blocking code offloaded to threadpool)"""
    service = ConcurrencyLabService()
    return await service.run_io_blocking_right(delay_ms=delay_ms)


@router.post(
    "/cpu-heavy",
    response_model=CpuHeavyJobStatusResponse,
    status_code=202,
    summary="Offload CPU-heavy report generation to ProcessPoolExecutor and return a job ID",
)
async def lab_cpu_heavy(
    payload: CpuHeavyJobCreateRequest,
) -> CpuHeavyJobStatusResponse:
    """# CONCEPT: async/await in FastAPI (CPU-bound work offloaded to ProcessPoolExecutor)"""
    service = ConcurrencyLabService()
    return await service.submit_cpu_heavy_job(rows_to_process=payload.rows_to_process)


@router.get(
    "/jobs/{job_id}",
    response_model=CpuHeavyJobStatusResponse,
    summary="Poll status of a CPU-heavy background job",
)
async def lab_get_job_status(job_id: str) -> CpuHeavyJobStatusResponse:
    service = ConcurrencyLabService()
    return service.get_job_status(job_id)
