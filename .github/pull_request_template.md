## Summary

Briefly describe what this PR introduces and why.

## Concept(s) Demonstrated
- [ ] Concept 1: Next.js `<Image>` vs `<img>`
- [ ] Concept 2: Server-side Paginated/Sortable/Filterable Table
- [ ] Concept 3: `async/await` in FastAPI (Concurrency Lab)
- [ ] Concept 4: Error Handling & Unified Error Envelope
- [ ] Concept 5: Caching Expensive Aggregates (Redis + Materialized View)
- [ ] Concept 6: Offset/Limit vs Keyset (Cursor) Pagination
- [ ] Concept 7: Reliable Structured JSON from LLMs
- [ ] Concept 8: Controlling LLM Cost in Production
- [ ] Concept 9: Shipping Speed vs Code Quality
- [ ] Concept 10: Maintainable Layered Architecture

## Quality & Non-Negotiables Checklist
- [ ] **Tests Added**: Unit/integration tests cover new business logic and API endpoints.
- [ ] **Error Handling**: Exceptions inherit from `AppError` and return the unified error envelope with `request_id`.
- [ ] **Input Validation**: All request bodies/params validated strictly with Pydantic v2 (no raw SQL interpolation).
- [ ] **Type Safety**: `mypy` (backend) and `tsc` (frontend, zero `any`) pass cleanly.
- [ ] **Docs Updated**: Relevant ADRs, `INTERVIEW_NOTES.md`, or `TECH_DEBT.md` updated.
- [ ] **No Secrets**: Verified zero API keys, tokens, or credentials committed.

