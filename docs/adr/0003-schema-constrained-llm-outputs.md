# ADR 0003: Schema-Constrained LLM Outputs with Validation Feedback Retries

- **Status**: Accepted
- **Date**: 2026-11-10
- **Related Concept**: Concept 7 (`/smart-capture`)

## Context
"Smart Lead Capture" extracts structured CRM fields (`name`, `email`, `phone`, `city`, `interest`, `budget`, `urgency`, `confidence`) from messy WhatsApp messages and emails. Relying on prompt instructions alone (`"Please return JSON"`) causes production outages when models wrap JSON in markdown fences, add conversational prose, or hallucinate invalid enum values.

## Decision
1. Define a strict Pydantic v2 model `ExtractedLead` (`extra="forbid"`, `EmailStr`, `UrgencyLevel` Enum, bounded `confidence` float) as the single source of truth.
2. Pass `ExtractedLead.model_json_schema()` directly into the LLM provider's tool-calling / structured-output parameter.
3. Defensively strip markdown fences and surrounding prose before calling `ExtractedLead.model_validate_json()`.
4. On validation failure, retry up to **2 times**, appending the exact Pydantic validation error to the prompt so the model self-corrects. If all retries fail, raise `ExternalServiceError` (HTTP 502) in our canonical error envelope.

## Consequences
- **Positive**: Guarantees 100% schema-valid objects reach the database or UI form, with full observability of retry counts and reasons in structured logs.
- **Negative / Trade-off**: Failed validations incur up to 2 additional LLM calls (bounded by `FEATURE_SMART_CAPTURE_RETRY` and per-user rate/budget limits).
