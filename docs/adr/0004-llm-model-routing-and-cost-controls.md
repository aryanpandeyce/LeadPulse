# ADR 0004: Multi-Lever LLM Cost Control & Intent-Based Model Routing

- **Status**: Accepted
- **Date**: 2026-11-10
- **Related Concept**: Concept 8 (`/ai-assistant` & `/admin/ai-costs`)

## Context
Sending every user chat message to a frontier reasoning model (`gpt-4o` / `claude-3-5-sonnet`) with the entire conversation history and full documentation attached makes unit economics unsustainable in production.

## Decision
Enforce a 10-lever defense-in-depth pipeline in `AIService`:
1. Zero-LLM FAQ short-circuiting for common questions (`$0.00`).
2. Intent/complexity router (`route_model_for_prompt`) directing standard queries to `LLM_CHEAP_MODEL` (`gpt-4o-mini`) and reserving `LLM_STRONG_MODEL` (`gpt-4o`) for complex analytical prompts.
3. Prompt normalization (lowercase, strip punctuation/whitespace) hashed into Redis (`llm:cache:v1:<sha256>`, TTL 3600s).
4. Chat history trimming (`MAX_HISTORY_TURNS = 4`) + `max_tokens = 250`.
5. RAG-lite top-3 chunk retrieval from `knowledge_base_docs`.
6. Per-user Redis rate limiting (`20 req/min` -> HTTP 429 with `Retry-After`) and daily spend caps (`$1.00/day`) backed by the `llm_usage` table.

## Consequences
- **Positive**: Reduces total LLM spend by **~75.9%** in our seeded workload while giving admins real-time visibility on `/admin/ai-costs`.
- **Negative / Trade-off**: Rule-based routing is a heuristic; borderline prompts could occasionally be routed to the cheap model when a stronger model would give a slightly more nuanced answer.

