# ADR 0001: Keyset (Cursor) Pagination vs Offset/Limit Pagination

- **Status**: Accepted
- **Date**: 2026-11-10
- **Related Concept**: Concept 2 (`/customers`) & Concept 6 (`/leads`)

## Context
LeadPulse manages two primary collections with very different access patterns and cardinalities:
1. **Customers Directory (`/customers`)**: ~10,000 rows, used by admins who need total row counts, arbitrary column sorting, and direct "Jump to Page N" controls.
2. **Leads Activity Feed (`/leads`)**: 200,000 to 1,000,000 rows, consumed as a chronological infinite-scroll feed where new leads are inserted continuously.

## Decision
- Use **Offset/Limit pagination** (`GET /api/v1/customers?page=1&limit=50`) with B-tree and `pg_trgm` GIN indexes for `/customers`.
- Use **Keyset (Cursor) pagination** (`GET /api/v1/leads?limit=50&cursor=<base64>`) backed by a composite index `(created_at DESC, id DESC)` and row-value comparison `WHERE (created_at, id) < (:cursor_ts, :cursor_id)` for `/leads`.

## Consequences
- **Positive**: Deep pagination on 200k+ leads runs in constant $O(1)$ time (~0.88 ms at page 4,000 vs ~94.7 ms with `OFFSET 199950`, a **107x speedup**). Real-time lead insertions never cause duplicate or skipped items in the infinite scroll feed.
- **Negative / Trade-off**: Keyset cursors cannot jump directly to an arbitrary page number without an intermediate index lookup, and require a unique tiebreaker column (`id DESC`) alongside `created_at DESC`.

