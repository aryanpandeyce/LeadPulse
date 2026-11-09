"""Pydantic v2 schemas for Concept 7 (Smart Lead Capture) and Concept 8 (AI Assistant & Cost Analytics).

# CONCEPT: Reliable structured JSON from an LLM (Pydantic model `ExtractedLead` as single source of truth)
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExtractedLead(BaseModel):
    """Single source of truth schema passed to LLM tool-use / structured outputs
    and validated with `ExtractedLead.model_validate_json()`.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150, description="Full name of the prospect")
    email: EmailStr | None = Field(
        default=None, description="Valid email address if present in message, else null"
    )
    phone: str | None = Field(
        default=None, description="Phone or WhatsApp number if present, else null"
    )
    city: str | None = Field(default=None, description="City or location mentioned, else null")
    interest: str = Field(
        min_length=2,
        max_length=300,
        description="Product, plan, or service the prospect is interested in",
    )
    budget: float | None = Field(
        default=None,
        ge=0,
        description="Estimated numeric budget in USD if mentioned, else null",
    )
    urgency: UrgencyLevel = Field(
        description="Urgency level inferred from timeline: low | medium | high"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0 for the extraction",
    )


class SmartCaptureRequest(BaseModel):
    raw_text: str = Field(
        min_length=5,
        max_length=4000,
        description="Unstructured WhatsApp, email, or call transcript text",
    )


class SmartCaptureResponse(BaseModel):
    extracted: ExtractedLead
    model_used: str
    retries_used: int = Field(ge=0, le=2)
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1500)
    history: list[ChatTurn] = Field(default_factory=list)


class AssistantDebugTelemetry(BaseModel):
    route_reason: str
    chosen_model: str
    short_circuited: bool
    cache_hit: bool
    normalized_cache_key: str
    rag_chunks_used: list[str]
    history_turns_kept: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    user_daily_spend_usd: float
    user_daily_budget_usd: float
    latency_ms: float


class AssistantChatResponse(BaseModel):
    answer: str
    telemetry: AssistantDebugTelemetry


class DailyCostPoint(BaseModel):
    date: str
    cost_usd: float
    requests: int
    cached_requests: int


class FeatureCostItem(BaseModel):
    feature: str
    requests: int
    cost_usd: float
    total_tokens: int


class UserCostItem(BaseModel):
    user_id: int | None
    requests: int
    cost_usd: float


class ModelCostItem(BaseModel):
    model: str
    requests: int
    cost_usd: float


class AiCostDashboardResponse(BaseModel):
    total_requests: int
    cache_hits: int
    cache_hit_rate_pct: float
    total_cost_usd: float
    estimated_saved_by_cache_and_routing_usd: float
    cost_by_day: list[DailyCostPoint]
    cost_by_feature: list[FeatureCostItem]
    cost_by_user: list[UserCostItem]
    cost_by_model: list[ModelCostItem]
    recent_logs: list[dict[str, str | int | float | bool | datetime | None]]
