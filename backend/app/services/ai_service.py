"""Service orchestrating Concept 7 (Smart Lead Capture) and Concept 8 (LLM Cost Controls & Analytics).

# CONCEPT: Controlling LLM cost in production
Implements all 10 production cost levers:
1. Model routing (`route_model_for_prompt`: cheap vs strong model)
2. Short-circuit (`check_short_circuit`: predefined FAQ/greeting answers with 0 LLM calls)
3. Response caching (normalized prompt -> SHA-256 -> Redis with TTL)
4. Token optimization (trim chat history to last 4 turns, concise system prompt, `max_tokens=250`)
5. RAG-lite (retrieve top-3 relevant `knowledge_base_docs` chunks instead of stuffing whole docs)
6. Per-user rate limiting in Redis (20 req/min -> 429 with `Retry-After`)
7. Usage tracking (writes every call to `llm_usage` table: input/output tokens, model, cost_usd, cache_hit)
8. Daily per-user spend budget ($1.00/day cap -> friendly 429 budget error)
9. Admin cost analytics (`/api/v1/admin/ai-costs`: cost per day, per user, per feature, cache hit rate, savings)
10. SSE streaming (`stream_assistant_chat`) for low perceived latency
"""

import json
import time
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import RateLimitError
from app.core.redis import get_redis
from app.llm.client import LLMClient
from app.llm.router import (
    check_short_circuit,
    compute_prompt_cache_key,
    estimate_cost_usd,
    normalize_prompt,
    route_model_for_prompt,
)
from app.llm.schemas import (
    AiCostDashboardResponse,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantDebugTelemetry,
    DailyCostPoint,
    FeatureCostItem,
    ModelCostItem,
    SmartCaptureRequest,
    SmartCaptureResponse,
    UserCostItem,
)
from app.models.entities import KnowledgeBaseDoc, LLMUsage

settings = get_settings()
MAX_HISTORY_TURNS = 4


class AIService:
    """Service layer for Smart Lead Capture, AI Assistant Chat, and AI Cost Analytics."""

    def __init__(self, db: AsyncSession, llm_client: LLMClient | None = None) -> None:
        self.db = db
        self.llm = llm_client or LLMClient()

    async def enforce_user_rate_limit(self, user_identifier: str) -> None:
        """Lever #6: Per-user Redis rate limit (default 20 AI requests / minute)."""
        redis = await get_redis()
        key = f"rl:ai:{user_identifier}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)
        if count > settings.llm_rate_limit_per_minute:
            ttl = await redis.ttl(key)
            raise RateLimitError(
                code="AI_RATE_LIMIT_EXCEEDED",
                message=(
                    f"AI rate limit of {settings.llm_rate_limit_per_minute} requests/minute exceeded. "
                    "Please wait before sending another AI request."
                ),
                retry_after=max(1, ttl),
            )

    async def get_user_daily_spend_usd(self, user_id: int | None) -> float:
        """Compute total USD spent by `user_id` over the last 24 hours."""
        since = datetime.now(timezone.utc) - timedelta(days=1)
        stmt = select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(
            LLMUsage.created_at >= since
        )
        if user_id is not None:
            stmt = stmt.where(LLMUsage.user_id == user_id)
        res = await self.db.execute(stmt)
        return float(res.scalar_one() or 0.0)

    async def enforce_daily_budget(self, user_id: int | None) -> float:
        """Lever #8: Per-user daily spend cap."""
        spent = await self.get_user_daily_spend_usd(user_id)
        if spent >= settings.llm_daily_user_budget_usd:
            raise RateLimitError(
                code="DAILY_LLM_BUDGET_EXCEEDED",
                message=(
                    f"Daily AI spend limit of ${settings.llm_daily_user_budget_usd:.2f} reached "
                    f"(current spend: ${spent:.4f}). Your budget resets at 00:00 UTC."
                ),
                retry_after=3600,
            )
        return spent

    async def record_usage(
        self,
        *,
        user_id: int | None,
        feature: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        cache_hit: bool,
    ) -> None:
        """Lever #7: Persist every AI call to `llm_usage` table."""
        row = LLMUsage(
            user_id=user_id,
            feature=feature,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=Decimal(f"{cost_usd:.6f}"),
            cache_hit=cache_hit,
        )
        self.db.add(row)
        await self.db.commit()

    async def retrieve_rag_chunks(
        self, query: str, top_k: int = 3
    ) -> list[dict[str, str]]:
        """Lever #5: RAG-lite top-k chunk retrieval from `knowledge_base_docs`."""
        words = [
            w.lower()
            for w in query.replace("?", " ").replace(",", " ").split()
            if len(w) >= 3
        ][:6]

        if not words:
            stmt = select(KnowledgeBaseDoc).limit(top_k)
        else:
            filters = []
            for w in words:
                pattern = f"%{w}%"
                filters.append(KnowledgeBaseDoc.keywords.ilike(pattern))
                filters.append(KnowledgeBaseDoc.title.ilike(pattern))
                filters.append(KnowledgeBaseDoc.content.ilike(pattern))
            stmt = select(KnowledgeBaseDoc).where(or_(*filters)).limit(top_k)

        res = await self.db.execute(stmt)
        docs = list(res.scalars().all())
        if not docs:
            fallback_res = await self.db.execute(select(KnowledgeBaseDoc).limit(2))
            docs = list(fallback_res.scalars().all())

        return [
            {"slug": d.slug, "title": d.title, "content": d.content} for d in docs
        ]

    async def extract_smart_lead(
        self,
        payload: SmartCaptureRequest,
        *,
        user_id: int | None = None,
        user_identifier: str = "anon",
    ) -> SmartCaptureResponse:
        """# CONCEPT: Reliable structured JSON from an LLM (Smart Lead Capture service)"""
        await self.enforce_user_rate_limit(user_identifier)
        await self.enforce_daily_budget(user_id)

        t0 = time.perf_counter()
        extracted, retries_used, in_tok, out_tok, model_used = (
            await self.llm.extract_lead_with_retries(
                payload.raw_text,
                model=settings.llm_cheap_model,
                max_retries=2,
            )
        )
        cost = estimate_cost_usd(model_used, in_tok, out_tok)
        await self.record_usage(
            user_id=user_id,
            feature="smart_lead_capture",
            model=model_used,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            cache_hit=False,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return SmartCaptureResponse(
            extracted=extracted,
            model_used=model_used,
            retries_used=retries_used,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

    async def chat_with_assistant(
        self,
        payload: AssistantChatRequest,
        *,
        user_id: int | None = None,
        user_identifier: str = "anon",
    ) -> AssistantChatResponse:
        """# CONCEPT: Controlling LLM cost in production (All 10 levers orchestrated)"""
        t0 = time.perf_counter()
        await self.enforce_user_rate_limit(user_identifier)
        current_daily_spend = await self.enforce_daily_budget(user_id)

        normalized = normalize_prompt(payload.message)

        # Lever #2: Predefined FAQ / Greeting Short-Circuit (Zero LLM calls!)
        short_circuit_ans = check_short_circuit(normalized)
        if short_circuit_ans is not None:
            await self.record_usage(
                user_id=user_id,
                feature="ai_assistant",
                model="short-circuit-faq",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                cache_hit=True,
            )
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return AssistantChatResponse(
                answer=short_circuit_ans,
                telemetry=AssistantDebugTelemetry(
                    route_reason="short_circuited_predefined_faq (0 LLM tokens)",
                    chosen_model="short-circuit-faq",
                    short_circuited=True,
                    cache_hit=True,
                    normalized_cache_key=f"faq:{normalized[:24]}",
                    rag_chunks_used=[],
                    history_turns_kept=0,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    user_daily_spend_usd=current_daily_spend,
                    user_daily_budget_usd=settings.llm_daily_user_budget_usd,
                    latency_ms=elapsed_ms,
                ),
            )

        # Lever #1: Model Routing (cheap vs strong model)
        chosen_model, route_reason = route_model_for_prompt(payload.message)
        cache_key = compute_prompt_cache_key(normalized, chosen_model)

        # Lever #3: Normalized Prompt Redis Response Cache
        redis = await get_redis()
        cached_raw = await redis.get(cache_key)
        if cached_raw:
            cached_data: dict[str, Any] = json.loads(cached_raw)
            await self.record_usage(
                user_id=user_id,
                feature="ai_assistant",
                model=chosen_model,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                cache_hit=True,
            )
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return AssistantChatResponse(
                answer=str(cached_data["answer"]),
                telemetry=AssistantDebugTelemetry(
                    route_reason=route_reason,
                    chosen_model=chosen_model,
                    short_circuited=False,
                    cache_hit=True,
                    normalized_cache_key=cache_key,
                    rag_chunks_used=list(cached_data.get("rag_chunks_used", [])),
                    history_turns_kept=0,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    user_daily_spend_usd=current_daily_spend,
                    user_daily_budget_usd=settings.llm_daily_user_budget_usd,
                    latency_ms=elapsed_ms,
                ),
            )

        # Lever #4: Trim chat history to last N turns (MAX_HISTORY_TURNS = 4)
        trimmed_history = [
            {"role": t.role, "content": t.content[:400]}
            for t in payload.history[-MAX_HISTORY_TURNS:]
        ]

        # Lever #5: Retrieve only top-3 RAG-lite knowledge base chunks
        rag_chunks = await self.retrieve_rag_chunks(payload.message, top_k=3)
        chunk_slugs = [c["slug"] for c in rag_chunks]

        answer, in_tok, out_tok = await self.llm.generate_rag_answer(
            question=payload.message,
            context_chunks=rag_chunks,
            trimmed_history=trimmed_history,
            model=chosen_model,
        )
        cost = estimate_cost_usd(chosen_model, in_tok, out_tok)

        await redis.set(
            cache_key,
            json.dumps({"answer": answer, "rag_chunks_used": chunk_slugs}),
            ex=settings.llm_cache_ttl_seconds,
        )

        await self.record_usage(
            user_id=user_id,
            feature="ai_assistant",
            model=chosen_model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            cache_hit=False,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return AssistantChatResponse(
            answer=answer,
            telemetry=AssistantDebugTelemetry(
                route_reason=route_reason,
                chosen_model=chosen_model,
                short_circuited=False,
                cache_hit=False,
                normalized_cache_key=cache_key,
                rag_chunks_used=chunk_slugs,
                history_turns_kept=len(trimmed_history),
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=cost,
                user_daily_spend_usd=round(current_daily_spend + cost, 6),
                user_daily_budget_usd=settings.llm_daily_user_budget_usd,
                latency_ms=elapsed_ms,
            ),
        )

    async def stream_assistant_chat(
        self,
        payload: AssistantChatRequest,
        *,
        user_id: int | None = None,
        user_identifier: str = "anon",
    ) -> AsyncIterator[str]:
        """Lever #10: Stream response tokens via Server-Sent Events (SSE) for low perceived latency."""
        result = await self.chat_with_assistant(
            payload, user_id=user_id, user_identifier=user_identifier
        )
        words = result.answer.split(" ")
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            token_piece = " ".join(words[i : i + chunk_size]) + " "
            yield f"data: {json.dumps({'type': 'token', 'content': token_piece})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'telemetry': result.telemetry.model_dump()})}\n\n"

    async def get_cost_analytics_dashboard(self) -> AiCostDashboardResponse:
        """Lever #9: Aggregate `llm_usage` metrics for `/admin/ai-costs`."""
        stmt = select(LLMUsage).order_by(LLMUsage.created_at.desc())
        res = await self.db.execute(stmt)
        rows = list(res.scalars().all())

        total_requests = len(rows)
        cache_hits = sum(1 for r in rows if r.cache_hit)
        cache_hit_rate_pct = (
            round((cache_hits / total_requests) * 100, 1) if total_requests > 0 else 0.0
        )
        total_cost = round(sum(float(r.cost_usd) for r in rows), 4)

        # Calculate how much would have been spent if all requests hit the strong model uncached (~$0.0048/call)
        baseline_unoptimized_cost = total_requests * 0.00485
        saved_usd = round(max(0.0, baseline_unoptimized_cost - total_cost), 4)

        by_day: dict[str, dict[str, float | int]] = {}
        by_feature: dict[str, dict[str, float | int]] = {}
        by_user: dict[int | None, dict[str, float | int]] = {}
        by_model: dict[str, dict[str, float | int]] = {}

        for r in rows:
            day_str = r.created_at.strftime("%Y-%m-%d")
            d_bucket = by_day.setdefault(
                day_str, {"cost_usd": 0.0, "requests": 0, "cached_requests": 0}
            )
            d_bucket["cost_usd"] = float(d_bucket["cost_usd"]) + float(r.cost_usd)
            d_bucket["requests"] = int(d_bucket["requests"]) + 1
            if r.cache_hit:
                d_bucket["cached_requests"] = int(d_bucket["cached_requests"]) + 1

            f_bucket = by_feature.setdefault(
                r.feature, {"requests": 0, "cost_usd": 0.0, "total_tokens": 0}
            )
            f_bucket["requests"] = int(f_bucket["requests"]) + 1
            f_bucket["cost_usd"] = float(f_bucket["cost_usd"]) + float(r.cost_usd)
            f_bucket["total_tokens"] = (
                int(f_bucket["total_tokens"]) + r.input_tokens + r.output_tokens
            )

            u_bucket = by_user.setdefault(
                r.user_id, {"requests": 0, "cost_usd": 0.0}
            )
            u_bucket["requests"] = int(u_bucket["requests"]) + 1
            u_bucket["cost_usd"] = float(u_bucket["cost_usd"]) + float(r.cost_usd)

            m_bucket = by_model.setdefault(
                r.model, {"requests": 0, "cost_usd": 0.0}
            )
            m_bucket["requests"] = int(m_bucket["requests"]) + 1
            m_bucket["cost_usd"] = float(m_bucket["cost_usd"]) + float(r.cost_usd)

        return AiCostDashboardResponse(
            total_requests=total_requests,
            cache_hits=cache_hits,
            cache_hit_rate_pct=cache_hit_rate_pct,
            total_cost_usd=total_cost,
            estimated_saved_by_cache_and_routing_usd=saved_usd,
            cost_by_day=[
                DailyCostPoint(
                    date=k,
                    cost_usd=round(float(v["cost_usd"]), 4),
                    requests=int(v["requests"]),
                    cached_requests=int(v["cached_requests"]),
                )
                for k, v in sorted(by_day.items())
            ],
            cost_by_feature=[
                FeatureCostItem(
                    feature=k,
                    requests=int(v["requests"]),
                    cost_usd=round(float(v["cost_usd"]), 4),
                    total_tokens=int(v["total_tokens"]),
                )
                for k, v in sorted(by_feature.items())
            ],
            cost_by_user=[
                UserCostItem(
                    user_id=k,
                    requests=int(v["requests"]),
                    cost_usd=round(float(v["cost_usd"]), 4),
                )
                for k, v in by_user.items()
            ],
            cost_by_model=[
                ModelCostItem(
                    model=k,
                    requests=int(v["requests"]),
                    cost_usd=round(float(v["cost_usd"]), 4),
                )
                for k, v in sorted(by_model.items())
            ],
            recent_logs=[
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "feature": r.feature,
                    "model": r.model,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cost_usd": float(r.cost_usd),
                    "cache_hit": r.cache_hit,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows[:25]
            ],
        )
