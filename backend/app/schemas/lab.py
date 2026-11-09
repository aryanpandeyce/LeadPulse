"""Pydantic v2 schemas for Concept 3: async/await in FastAPI Concurrency Lab."""

from typing import Literal

from pydantic import BaseModel, Field


class LabIoResponse(BaseModel):
    mode: Literal["io_async_gather", "io_blocking_wrong", "io_blocking_right"]
    simulated_calls: int
    per_call_delay_ms: int
    elapsed_ms: float
    explanation: str


class CpuHeavyJobCreateRequest(BaseModel):
    rows_to_process: int = Field(default=50_000, ge=1_000, le=500_000)


class CpuHeavyJobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    rows_processed: int
    checksum: str | None = None
    elapsed_ms: float | None = None
    worker_type: str = "ProcessPoolExecutor"
