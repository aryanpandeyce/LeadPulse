# Controlling LLM Cost in Production: 10 Engineering Levers (Concept 8)

Unbounded LLM endpoints can easily burn thousands of dollars per day if a user scripts a loop, pastes massive chat histories, or triggers expensive reasoning models on trivial greetings.

LeadPulse implements **10 layered cost-control mechanisms** in `backend/app/llm/` and `backend/app/services/ai_service.py`:

| # | Cost Control Lever | Implementation in LeadPulse | Measured Impact on `/admin/ai-costs` |
| :-: | :--- | :--- | :--- |
| **1** | **Model Routing (Cheap vs Strong)** | `route_model_for_prompt()` sends standard lookups/extractions to `gpt-4o-mini` (`$0.15/1M` in) and routes only multi-factor analysis (`compare`, `analyze`, `architecture`, >45 words) to `gpt-4o` (`$2.50/1M` in). | **75% of calls** use the cheap model (**~10x cheaper per token**). |
| **2** | **Zero-LLM FAQ Short-Circuit** | `check_short_circuit()` intercepts high-frequency prompts (`"what is your company name"`, `"hello"`, `"what are the demo credentials"`) and returns instant verified answers. | **100% token savings ($0.00)** and `<1 ms` latency on common FAQs. |
| **3** | **Normalized Prompt Redis Caching** | `normalize_prompt()` lowercases, strips trailing punctuation, collapses whitespace, and hashes into `llm:cache:v1:<sha256>` with a 3,600s TTL. | **33.3% cache hit rate** in seeded production workload (`$0.00` on hits). |
| **4** | **Token & History Optimization** | Trims conversation history to the last `MAX_HISTORY_TURNS = 4` turns (max 400 chars/turn), uses a compact system prompt, and enforces `max_tokens = 250` on every completion call. | Caps worst-case prompt growth from $O(N)$ turns to a fixed **<600 token ceiling**. |
| **5** | **RAG-Lite Top-K Retrieval** | `retrieve_rag_chunks()` queries `knowledge_base_docs` and injects only the **top 3 relevant chunks** instead of stuffing the entire knowledge base into every prompt. | Reduces context tokens by **~65%** per query. |
| **6** | **Per-User Redis Rate Limiting** | `enforce_user_rate_limit()` enforces `20 requests/minute` per user/IP (`rl:ai:{user}`), returning HTTP `429` with `Retry-After` in our unified error envelope. | Blocks runaway loops and abuse bursts immediately. |
| **7** | **Granular Usage Tracking (`llm_usage`)** | Every call logs `user_id`, `feature`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, and `cache_hit` to PostgreSQL. | Full FinOps auditability by user, feature, day, and model. |
| **8** | **Per-User Daily Spend Budgets** | `enforce_daily_budget()` sums the user's rolling 24h `cost_usd` and blocks calls once `LLM_DAILY_USER_BUDGET_USD` (`$1.00/day`) is reached. | Guarantees a hard upper bound on daily financial exposure per seat. |
| **9** | **Admin FinOps Dashboard (`/admin/ai-costs`)** | Visualizes daily spend, cache hit rate %, cost by feature/model, and total dollars saved (`$0.4420` saved across 120 seeded calls, a **75.9% cost reduction** vs uncached `gpt-4o`). | Gives engineering & finance real-time visibility. |
| **10** | **SSE Response Streaming** | `POST /api/v1/ai/chat/stream` streams tokens progressively via `text/event-stream` (controlled by `FEATURE_AI_STREAMING`). | Reduces perceived Time-To-First-Token (TTFT) while keeping `max_tokens` bounded. |
