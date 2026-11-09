"""Model Router, Prompt Normalization, and Zero-LLM Short-Circuiting (Concept 8).

# CONCEPT: Controlling LLM cost in production
1. Short-circuit: Common FAQ/greeting prompts return predefined answers with ZERO LLM calls ($0.00).
2. Prompt normalization: Lowercase -> strip punctuation/extra whitespace -> SHA-256 hash for high Redis cache hit rates.
3. Model routing: Routes simple intents to `settings.llm_cheap_model` (gpt-4o-mini / claude-3-haiku)
   and complex reasoning/multi-factor analysis to `settings.llm_strong_model` (gpt-4o / claude-3-5-sonnet).
"""

import hashlib
import re

from app.core.config import get_settings

settings = get_settings()

# Predefined zero-cost responses for ultra-common questions (Lever #2: Short-circuit)
PREDEFINED_SHORT_CIRCUITS: dict[str, str] = {
    "what is your company name": (
        "Our company name is **LeadPulse CRM** — a production-grade mini CRM with an integrated AI Assistant."
    ),
    "who are you": (
        "I am the **LeadPulse AI Assistant**. I help sales teams capture leads, analyze pipeline KPIs, and search the CRM knowledge base."
    ),
    "hello": "Hello! How can I help you with your LeadPulse CRM pipeline or product questions today?",
    "hi": "Hi there! Ask me anything about LeadPulse pricing, Smart Lead Capture, pagination, or KPI caching.",
    "what are the demo credentials": (
        "Demo credentials are **Admin**: `admin@leadpulse.io` / `Admin@123` and **Sales Agent**: `agent@leadpulse.io` / `Agent@123`."
    ),
}

COMPLEX_INTENT_KEYWORDS = {
    "compare",
    "analyze",
    "strategy",
    "architecture",
    "trade-off",
    "tradeoff",
    "explain why",
    "summarize",
    "forecast",
    "deep dive",
    "optimize",
}


def normalize_prompt(prompt: str) -> str:
    """# CONCEPT: Controlling LLM cost in production (Prompt normalization for caching)
    Lowercase, trim, strip trailing question/exclamation marks, and collapse whitespace.
    Example: '  What is your COMPANY name??  ' -> 'what is your company name'
    """
    cleaned = prompt.strip().lower()
    cleaned = re.sub(r"[?!.,;]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def compute_prompt_cache_key(normalized_prompt: str, model: str) -> str:
    """Return a versioned Redis key for a normalized prompt."""
    digest = hashlib.sha256(f"{model}:{normalized_prompt}".encode()).hexdigest()[:24]
    return f"llm:cache:v1:{digest}"


def check_short_circuit(normalized_prompt: str) -> str | None:
    """Return a predefined response if the normalized prompt matches a known FAQ/greeting."""
    return PREDEFINED_SHORT_CIRCUITS.get(normalized_prompt)


def route_model_for_prompt(prompt: str) -> tuple[str, str]:
    """# CONCEPT: Controlling LLM cost in production (Model Routing: Cheap vs Strong)
    Returns `(chosen_model, route_reason)`.
    """
    lowered = prompt.lower()
    word_count = len(lowered.split())

    for kw in COMPLEX_INTENT_KEYWORDS:
        if kw in lowered:
            return (
                settings.llm_strong_model,
                f"routed_to_strong_model (matched complex reasoning keyword: '{kw}')",
            )

    if word_count > 45:
        return (
            settings.llm_strong_model,
            f"routed_to_strong_model (long multi-clause prompt: {word_count} words)",
        )

    return (
        settings.llm_cheap_model,
        "routed_to_cheap_model (standard FAQ / lookup intent)",
    )


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate realistic token cost in USD based on model tier."""
    if model == settings.llm_cheap_model or "mini" in model or "haiku" in model:
        # ~$0.15 / 1M input, $0.60 / 1M output (scaled slightly so dashboard numbers are clearly visible in demos)
        cost = (input_tokens * 0.0000015) + (output_tokens * 0.0000060)
    else:
        # Strong model (~10x more expensive than cheap model)
        cost = (input_tokens * 0.0000150) + (output_tokens * 0.0000600)
    return round(cost, 6)
