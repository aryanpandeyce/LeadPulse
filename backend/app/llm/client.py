"""Provider-agnostic LLM Client supporting OpenAI, Anthropic, and deterministic Mock mode.

# CONCEPT: Reliable structured JSON from an LLM
- Generates JSON Schema directly from `ExtractedLead.model_json_schema()`.
- Uses provider structured outputs / tool calling (`tools` with `input_schema` / `parameters`).
- Defensively strips markdown fences (```json ... ```) and leading/trailing prose as a last-resort parser.
- Validates strictly with `ExtractedLead.model_validate_json()`.
- On validation failure, retries up to 2 times, feeding the exact validation error back to the model:
  "Your previous output failed validation: <error>. Please return valid JSON matching the schema."
"""

import json
import logging
import re
from typing import Any

import httpx
from pydantic import ValidationError as PydanticValidationError

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.llm.schemas import ExtractedLead

logger = logging.getLogger(__name__)
settings = get_settings()


def strip_markdown_fences_and_prose(raw: str) -> str:
    """# CONCEPT: Reliable structured JSON from an LLM (Defensive parser for markdown fences & prose)
    Extracts the JSON object from responses wrapped in ```json ... ``` or surrounded by prose.
    """
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()
    return text


class LLMClient:
    """Provider-agnostic client for structured extraction and RAG-lite assistant chat."""

    def __init__(self) -> None:
        self.provider = settings.llm_provider

    async def call_structured_extraction(
        self,
        *,
        raw_text: str,
        model: str,
        validation_feedback: str | None = None,
    ) -> tuple[str, int, int]:
        """Invoke the configured LLM provider with `ExtractedLead.model_json_schema()` tool definition.
        Returns `(raw_json_string, input_tokens, output_tokens)`.
        """
        schema = ExtractedLead.model_json_schema()
        system_prompt = (
            "Extract lead information using the `record_extracted_lead` tool schema. "
            "Never invent emails or phone numbers not present in the text."
        )
        user_content = raw_text
        if validation_feedback:
            user_content = (
                f"{raw_text}\n\n[VALIDATION RETRY FEEDBACK]: Your previous output failed "
                f"Pydantic schema validation: {validation_feedback}. Fix the fields and return valid JSON."
            )

        if self.provider == "openai" and settings.openai_api_key:
            return await self._call_openai_tool(
                model=model,
                system_prompt=system_prompt,
                user_content=user_content,
                json_schema=schema,
            )

        if self.provider == "anthropic" and settings.anthropic_api_key:
            return await self._call_anthropic_tool(
                model=model,
                system_prompt=system_prompt,
                user_content=user_content,
                json_schema=schema,
            )

        # Deterministic heuristic extraction for local/portfolio demo without external API keys
        return self._deterministic_extract(raw_text)

    async def _call_openai_tool(
        self,
        *,
        model: str,
        system_prompt: str,
        user_content: str,
        json_schema: dict[str, Any],
    ) -> tuple[str, int, int]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": model,
                    "max_tokens": 350,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "record_extracted_lead",
                                "description": "Record structured CRM lead fields",
                                "parameters": json_schema,
                            },
                        }
                    ],
                    "tool_choice": {
                        "type": "function",
                        "function": {"name": "record_extracted_lead"},
                    },
                },
            )
            if resp.status_code >= 400:
                raise ExternalServiceError(
                    code="OPENAI_UPSTREAM_ERROR",
                    message=f"OpenAI API returned HTTP {resp.status_code}",
                )
            body = resp.json()
            usage = body.get("usage", {})
            tool_calls = body["choices"][0]["message"].get("tool_calls", [])
            args_str = (
                tool_calls[0]["function"]["arguments"]
                if tool_calls
                else body["choices"][0]["message"].get("content", "{}")
            )
            return (
                str(args_str),
                int(usage.get("prompt_tokens", 120)),
                int(usage.get("completion_tokens", 65)),
            )

    async def _call_anthropic_tool(
        self,
        *,
        model: str,
        system_prompt: str,
        user_content: str,
        json_schema: dict[str, Any],
    ) -> tuple[str, int, int]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model,
                    "max_tokens": 350,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_content}],
                    "tools": [
                        {
                            "name": "record_extracted_lead",
                            "description": "Record structured CRM lead fields",
                            "input_schema": json_schema,
                        }
                    ],
                    "tool_choice": {"type": "tool", "name": "record_extracted_lead"},
                },
            )
            if resp.status_code >= 400:
                raise ExternalServiceError(
                    code="ANTHROPIC_UPSTREAM_ERROR",
                    message=f"Anthropic API returned HTTP {resp.status_code}",
                )
            body = resp.json()
            usage = body.get("usage", {})
            for block in body.get("content", []):
                if block.get("type") == "tool_use":
                    return (
                        json.dumps(block.get("input", {})),
                        int(usage.get("input_tokens", 120)),
                        int(usage.get("output_tokens", 65)),
                    )
            return "{}", 120, 40

    def _deterministic_extract(self, raw_text: str) -> tuple[str, int, int]:
        """Parse messy WhatsApp/email text into `ExtractedLead` JSON for zero-key local demos."""
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw_text)
        phone_match = re.search(r"(\+?\d[\d\s-]{7,15}\d)", raw_text)
        budget_match = re.search(
            r"(?:\$|usd|budget\s*(?:is|of|:)?\s*\$?)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(k)?",
            raw_text,
            flags=re.IGNORECASE,
        )

        budget_val: float | None = None
        if budget_match:
            num = float(budget_match.group(1).replace(",", ""))
            if budget_match.group(2):
                num *= 1000
            budget_val = num

        city_val: str | None = None
        for candidate in (
            "Ahmedabad",
            "Bengaluru",
            "Mumbai",
            "Delhi",
            "Pune",
            "Hyderabad",
            "Chennai",
            "London",
            "New York",
        ):
            if candidate.lower() in raw_text.lower():
                city_val = candidate
                break

        name_match = re.search(
            r"(?:hi|hello|hey)?\s*(?:i am|i'm|this is|name is|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            raw_text,
        )
        name_val = name_match.group(1).strip() if name_match else "Vikram Patel"

        lowered = raw_text.lower()
        if any(w in lowered for w in ("urgent", "asap", "immediately", "today", "this week")):
            urgency = "high"
        elif any(w in lowered for w in ("next month", "q3", "exploring", "later")):
            urgency = "low"
        else:
            urgency = "medium"

        payload = {
            "name": name_val,
            "email": email_match.group(0) if email_match else None,
            "phone": phone_match.group(1).strip() if phone_match else None,
            "city": city_val,
            "interest": "LeadPulse Growth & AI Copilot Suite",
            "budget": budget_val,
            "urgency": urgency,
            "confidence": 0.92 if (email_match or phone_match) else 0.76,
        }
        in_tokens = max(45, len(raw_text.split()) * 2)
        out_tokens = 68
        return json.dumps(payload), in_tokens, out_tokens

    async def extract_lead_with_retries(
        self,
        raw_text: str,
        *,
        model: str | None = None,
        max_retries: int = 2,
    ) -> tuple[ExtractedLead, int, int, int, str]:
        """# CONCEPT: Reliable structured JSON from an LLM
        1. Calls LLM with `ExtractedLead` JSON schema.
        2. Strips markdown fences / prose defensively.
        3. Validates with `ExtractedLead.model_validate_json()`.
        4. On failure, retries up to `max_retries` (2) times feeding the validation error back to the model.
        5. Raises `ExternalServiceError` (HTTP 502) in our unified error envelope if all retries fail.
        """
        chosen_model = model or settings.llm_cheap_model
        total_in = 0
        total_out = 0
        feedback: str | None = None
        effective_retries = max_retries if settings.feature_smart_capture_retry else 0

        for attempt in range(effective_retries + 1):
            raw_output, in_tok, out_tok = await self.call_structured_extraction(
                raw_text=raw_text,
                model=chosen_model,
                validation_feedback=feedback,
            )
            total_in += in_tok
            total_out += out_tok

            cleaned_json = strip_markdown_fences_and_prose(raw_output)
            try:
                validated = ExtractedLead.model_validate_json(cleaned_json)
                return validated, attempt, total_in, total_out, chosen_model
            except (PydanticValidationError, ValueError) as exc:
                feedback = str(exc)
                logger.warning(
                    "LLM structured output failed validation",
                    extra={
                        "extra_data": {
                            "attempt": attempt + 1,
                            "max_retries": effective_retries,
                            "reason": feedback[:300],
                        }
                    },
                )

        raise ExternalServiceError(
            code="LLM_SCHEMA_VALIDATION_FAILED",
            message="LLM output failed schema validation after maximum retries.",
            details=[{"field": "extracted_lead", "issue": (feedback or "Invalid JSON")[:250]}],
        )

    async def generate_rag_answer(
        self,
        *,
        question: str,
        context_chunks: list[dict[str, str]],
        trimmed_history: list[dict[str, str]],
        model: str,
    ) -> tuple[str, int, int]:
        """# CONCEPT: Controlling LLM cost in production (Token optimization + max_tokens + RAG-lite chunks)"""
        context_text = "\n\n".join(
            f"[{c['title']}]: {c['content']}" for c in context_chunks
        )
        # Keep system prompt concise to minimize input token burn
        system_prompt = (
            "You are LeadPulse AI Assistant. Answer concisely using ONLY the provided KB chunks.\n"
            f"KB:\n{context_text}"
        )

        in_tokens = max(
            60,
            len((system_prompt + " " + question).split())
            + sum(len(m["content"].split()) for m in trimmed_history),
        )

        if self.provider == "openai" and settings.openai_api_key:
            async with httpx.AsyncClient(timeout=20.0) as client:
                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(trimmed_history)
                messages.append({"role": "user", "content": question})
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": 250,
                    },
                )
                if resp.status_code < 400:
                    data = resp.json()
                    ans = str(data["choices"][0]["message"]["content"])
                    u = data.get("usage", {})
                    return (
                        ans,
                        int(u.get("prompt_tokens", in_tokens)),
                        int(u.get("completion_tokens", 85)),
                    )

        # Deterministic grounded synthesis from retrieved RAG-lite chunks
        if context_chunks:
            synthesized = " ".join(
                f"**{c['title']}**: {c['content']}" for c in context_chunks
            )
            answer = (
                f"Based on the LeadPulse Knowledge Base ({len(context_chunks)} relevant chunk(s) retrieved):\n\n"
                f"{synthesized}"
            )
        else:
            answer = (
                "LeadPulse CRM helps teams manage 10k+ customers and 200k+ leads with "
                "Smart Lead Capture, Keyset Pagination, and layered Redis + Materialized View caching."
            )
        out_tokens = max(35, len(answer.split()))
        return answer, in_tokens, out_tokens

