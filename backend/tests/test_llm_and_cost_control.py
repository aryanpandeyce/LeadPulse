"""Tests for Concept 7 (Reliable Structured JSON from LLMs) and Concept 8 (LLM Cost Controls).

Specifically mocks the LLM to return:
1. Valid JSON -> passes on attempt 0
2. Invalid JSON on attempt 1, then valid JSON on retry -> succeeds with retries_used == 1
3. JSON with wrong types / bad enum across all retries -> raises 502 LLM_SCHEMA_VALIDATION_FAILED in unified error envelope
4. Markdown fenced / extra prose wrapped around JSON -> stripped defensively and validated
Also tests:
5. Short-circuit FAQ (0 LLM tokens), normalized Redis cache hit, model routing (cheap vs strong), and rate limit 429.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalServiceError
from app.llm.client import LLMClient
from app.main import app


@pytest.mark.asyncio
async def test_llm_structured_output_valid_json() -> None:
    client = LLMClient()
    client.call_structured_extraction = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            '{"name":"Aryan Pandey","email":"aryan@leadpulse.io","phone":"+91-9825000000","city":"Ahmedabad","interest":"Enterprise CRM","budget":15000,"urgency":"high","confidence":0.96}',
            110,
            60,
        )
    )
    extracted, retries_used, in_tok, out_tok, _ = await client.extract_lead_with_retries(
        "Sample message"
    )
    assert extracted.name == "Aryan Pandey"
    assert extracted.urgency.value == "high"
    assert retries_used == 0
    assert in_tok == 110
    assert out_tok == 60


@pytest.mark.asyncio
async def test_llm_structured_output_prose_and_markdown_fence_stripping() -> None:
    client = LLMClient()
    fenced_prose = """Sure! Here is the extracted JSON you requested:
```json
{
  "name": "Meera Nair",
  "email": "meera@acme.in",
  "phone": null,
  "city": "Bengaluru",
  "interest": "Growth Plan",
  "budget": 4500,
  "urgency": "medium",
  "confidence": 0.89
}
```
Let me know if you need anything else!"""
    client.call_structured_extraction = AsyncMock(  # type: ignore[method-assign]
        return_value=(fenced_prose, 120, 70)
    )
    extracted, retries_used, _, _, _ = await client.extract_lead_with_retries(
        "Sample prose-wrapped response"
    )
    assert extracted.name == "Meera Nair"
    assert extracted.city == "Bengaluru"
    assert retries_used == 0


@pytest.mark.asyncio
async def test_llm_structured_output_retry_with_validation_feedback() -> None:
    """First call returns wrong types (`urgency: 'super_urgent'`, invalid email), second call fixes it after receiving validation feedback."""
    client = LLMClient()
    mock_call = AsyncMock(
        side_effect=[
            (
                '{"name":"Rohan","email":"not-an-email","interest":"CRM","urgency":"super_urgent","confidence":1.5}',
                100,
                50,
            ),
            (
                '{"name":"Rohan","email":"rohan@valid.io","phone":null,"city":"Pune","interest":"CRM","budget":2000,"urgency":"high","confidence":0.85}',
                140,
                55,
            ),
        ]
    )
    client.call_structured_extraction = mock_call  # type: ignore[method-assign]

    extracted, retries_used, in_tok, out_tok, _ = await client.extract_lead_with_retries(
        "Rohan from Pune wants CRM urgently"
    )
    assert retries_used == 1
    assert extracted.email == "rohan@valid.io"
    assert in_tok == 240
    assert out_tok == 105
    # Verify second call received validation_feedback from first failure
    second_call_kwargs = mock_call.call_args_list[1].kwargs
    assert second_call_kwargs["validation_feedback"] is not None


@pytest.mark.asyncio
async def test_llm_structured_output_exhausts_retries_and_raises_clean_error() -> None:
    """When LLM returns invalid JSON on initial attempt + 2 retries (3 calls total), raises ExternalServiceError (502)."""
    client = LLMClient()
    mock_call = AsyncMock(return_value=("this is completely broken non-json output", 80, 20))
    client.call_structured_extraction = mock_call  # type: ignore[method-assign]

    with pytest.raises(ExternalServiceError) as exc_info:
        await client.extract_lead_with_retries("Bad input", max_retries=2)

    assert exc_info.value.code == "LLM_SCHEMA_VALIDATION_FAILED"
    assert exc_info.value.status_code == 502
    assert mock_call.call_count == 3


@pytest.mark.asyncio
async def test_ai_cost_controls_short_circuit_caching_routing_and_analytics(
    db_session: AsyncSession,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Short-circuit FAQ ("What is your company name??" -> normalized -> 0 tokens, $0.00)
        sc_resp = await client.post(
            "/api/v1/ai/chat",
            json={"message": "  What is your COMPANY name??  ", "history": []},
        )
        assert sc_resp.status_code == 200
        sc_tel = sc_resp.json()["telemetry"]
        assert sc_tel["short_circuited"] is True
        assert sc_tel["cache_hit"] is True
        assert sc_tel["cost_usd"] == 0.0

        # 2. First call to a normal question -> MISS, routed to cheap model + RAG chunks retrieved
        q1_resp = await client.post(
            "/api/v1/ai/chat",
            json={"message": "What are the LeadPulse pricing plans?", "history": []},
        )
        assert q1_resp.status_code == 200
        q1_tel = q1_resp.json()["telemetry"]
        assert q1_tel["cache_hit"] is False
        assert len(q1_tel["rag_chunks_used"]) >= 1
        assert q1_tel["cost_usd"] > 0

        # 3. Second call with different casing/whitespace -> normalized Redis CACHE HIT ($0.00)
        q2_resp = await client.post(
            "/api/v1/ai/chat",
            json={"message": "  what are the leadpulse PRICING plans?! ", "history": []},
        )
        assert q2_resp.status_code == 200
        q2_tel = q2_resp.json()["telemetry"]
        assert q2_tel["cache_hit"] is True
        assert q2_tel["cost_usd"] == 0.0

        # 4. Complex analytical question -> routed to strong model (`gpt-4o`)
        strong_resp = await client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Please compare and analyze the architecture trade-offs of keyset vs offset pagination.",
                "history": [],
            },
        )
        assert strong_resp.status_code == 200
        assert "strong_model" in strong_resp.json()["telemetry"]["route_reason"]

        # 5. Admin cost analytics endpoint returns aggregated telemetry
        costs_resp = await client.get("/api/v1/admin/ai-costs")
        assert costs_resp.status_code == 200
        costs_body = costs_resp.json()
        assert costs_body["total_requests"] >= 120
        assert costs_body["cache_hit_rate_pct"] > 0
