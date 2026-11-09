# Issue #001: Upgrade RAG-Lite to Hybrid Search (`pgvector` + Full-Text RRF)

- **Status**: Deferred (Phase 2)
- **Labels**: `enhancement`, `ai`, `database`
- **Related Tech Debt**: `TD-002`

## Context
Currently, `AIService.retrieve_rag_chunks()` retrieves the top-3 relevant chunks from `knowledge_base_docs` using keyword filtering. Because our `docker-compose.yml` already runs `pgvector/pgvector:pg16`, we can add dense vector embeddings without changing infrastructure.

## Acceptance Criteria
1. Enable `CREATE EXTENSION IF NOT EXISTS vector;` in an Alembic migration.
2. Add `embedding vector(1536)` and a `GIN (to_tsvector('english', content))` index to `knowledge_base_docs`.
3. Implement Reciprocal Rank Fusion (RRF) combining top-5 cosine similarity matches + top-5 full-text matches into the final top-3 chunks passed to the LLM.
