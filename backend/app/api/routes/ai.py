"""Thin API routes for Concept 7 (Smart Lead Capture) and Concept 8 (AI Assistant & Cost Control Dashboard)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import get_optional_user
from app.llm.schemas import (
    AiCostDashboardResponse,
    AssistantChatRequest,
    AssistantChatResponse,
    SmartCaptureRequest,
    SmartCaptureResponse,
)
from app.models.entities import User
from app.services.ai_service import AIService

router = APIRouter(tags=["AI Features & Cost Controls (Concepts 7 & 8)"])


def _resolve_user_identifier(request: Request, user: User | None) -> str:
    if user is not None:
        return f"user:{user.id}"
    client_ip = request.client.host if request.client else "anon"
    return f"ip:{client_ip}"


@router.post(
    "/ai/smart-capture",
    response_model=SmartCaptureResponse,
    summary="Extract structured Lead JSON from messy text using Pydantic schema tool-use + validation retries (Concept 7)",
)
async def smart_lead_capture(
    payload: SmartCaptureRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> SmartCaptureResponse:
    """# CONCEPT: Reliable structured JSON from an LLM"""
    service = AIService(db)
    return await service.extract_smart_lead(
        payload,
        user_id=current_user.id if current_user else None,
        user_identifier=_resolve_user_identifier(request, current_user),
    )


@router.post(
    "/ai/chat",
    response_model=AssistantChatResponse,
    summary="Chat with the CRM AI Assistant (Model routing, FAQ short-circuit, Redis cache, RAG-lite, budgets)",
)
async def ai_assistant_chat(
    payload: AssistantChatRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> AssistantChatResponse:
    """# CONCEPT: Controlling LLM cost in production"""
    service = AIService(db)
    return await service.chat_with_assistant(
        payload,
        user_id=current_user.id if current_user else None,
        user_identifier=_resolve_user_identifier(request, current_user),
    )


@router.post(
    "/ai/chat/stream",
    summary="Stream AI Assistant response via Server-Sent Events (SSE)",
)
async def ai_assistant_chat_stream(
    payload: AssistantChatRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Streams tokens using SSE (`text/event-stream`) and emits final cost/routing telemetry event."""
    service = AIService(db)
    return StreamingResponse(
        service.stream_assistant_chat(
            payload,
            user_id=current_user.id if current_user else None,
            user_identifier=_resolve_user_identifier(request, current_user),
        ),
        media_type="text/event-stream",
    )


@router.get(
    "/admin/ai-costs",
    response_model=AiCostDashboardResponse,
    summary="Admin AI Cost Analytics: daily spend, cache hit rate, per-feature & per-model breakdown",
)
async def get_ai_cost_analytics(
    db: AsyncSession = Depends(get_db_session),
) -> AiCostDashboardResponse:
    """Returns real-time aggregation of `llm_usage` rows for `/admin/ai-costs`."""
    service = AIService(db)
    return await service.get_cost_analytics_dashboard()

