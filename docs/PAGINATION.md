# Offset/Limit vs Keyset (Cursor) Pagination (Concept 6)

LeadPulse uses **both** pagination strategies intentionally, picking the right tool for each UX requirement:

| Feature / Page | Strategy Chosen | Why |
| :--- | :--- | :--- |
| **Customers Directory (`/customers`)** | **Offset / Limit** (`PAGE` + `LIMIT`) | Admin tables require total row counts and direct "Jump to Page 14" navigation, and the dataset is bounded (10,000 rows). |
| **Leads Activity Feed (`/leads`)** | **Keyset / Cursor** (`cursor` + `limit`) | Infinite-scroll feed over **200,000+ leads** where users scroll chronologically and new leads arrive continuously in real time. |

---

## 1. How Keyset Pagination Works in LeadPulse

1. **Composite Index**: `CREATE INDEX ix_leads_created_at_id_desc ON leads (created_at DESC, id DESC);`
2. **Deterministic Tiebreaker**: `created_at` timestamps are **not unique** (multiple leads can be created in the same millisecond or batch). Including the unique primary key `id DESC` as a tiebreaker guarantees a strict, deterministic total ordering.
3. **Opaque Base64 Cursor**: The last row of each batch encodes `{"created_at": "2026-11-09T18:10:00+00:00", "id": 199950}` into URL-safe base64.
4. **Row-Value Predicate (`tuple_`)**:
   ```sql
   SELECT id, customer_id, name, email, source, status, revenue, created_at
   FROM leads
   WHERE (created_at, id) < (:cursor_created_at, :cursor_id)
   ORDER BY created_at DESC, id DESC
   LIMIT 51; -- Fetch limit + 1 to detect `has_more` without a COUNT(*) query
   ```

---

## 2. Why Deep `OFFSET` Degrades Linearly $O(N)$

When executing `OFFSET 199950 LIMIT 50` (Page 4,000), PostgreSQL must still walk through and discard the first **199,950 index/heap entries** before returning the 50 requested rows.

With Keyset pagination, PostgreSQL traverses the B-tree directly to `(created_at, id) < (:ts, :id)` in $O(\log N)$ tree depth + $O(K)$ page size, keeping query latency flat regardless of whether the user is on page 1 or page 4,000.

### Benchmark Results on 200,000 Leads (`limit = 50`)

> **Measured on**: Windows 10 (AMD64) / PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) / 10,000 customers, 200,000 leads, 500,000 activities / 2026-11-10  
> Raw outputs saved in [`docs/benchmarks/benchmark_pagination.txt`](benchmarks/benchmark_pagination.txt) and [`docs/benchmarks/explain_analyze_leads_keyset.txt`](benchmarks/explain_analyze_leads_keyset.txt).

| Depth (Rows Skipped) | End-to-End `OFFSET` (ms) | End-to-End Keyset (ms) | End-to-End Speedup | Postgres `EXPLAIN ANALYZE` (`OFFSET` vs Keyset) |
| ---: | ---: | ---: | ---: | :--- |
| **100** | `6.58 ms` | `7.35 ms` | `0.9x` | Both index-seek near top of tree |
| **1,000** | `5.00 ms` | `5.71 ms` | `0.9x` | Shallow scan |
| **10,000** | `6.33 ms` | `5.42 ms` | `1.2x` | `OFFSET` walks 10,050 entries |
| **50,000** | `11.01 ms` | `4.26 ms` | `2.6x` | `OFFSET` walks 50,050 entries |
| **100,000** | `15.19 ms` | `3.68 ms` | `4.1x` | `OFFSET` walks 100,050 entries |
| **150,000** | `18.28 ms` | `3.42 ms` | **`5.3x`** | **`83.28 ms` (3,016 buffers) vs `0.33 ms` (5 buffers) = `252x` faster in Postgres** |

---

## 3. Why Offset Duplicates or Skips Rows Under Real-Time Writes (Page Drift)

Suppose User A loads **Page 1** (`OFFSET 0 LIMIT 50`, showing Leads `#200,000` down to `#199,951`).
While User A is reading Page 1, **5 new leads** (`#200,005` .. `#200,001`) are inserted at the top of the feed.
When User A requests **Page 2** (`OFFSET 50 LIMIT 50`), rows `#199,955` through `#199,951` have shifted into positions 51–55 and are **returned a second time (duplicated)**! Conversely, if rows on Page 1 are deleted, Page 2 **silently skips rows**.

Because Keyset pagination anchors directly to the last seen row `WHERE (created_at, id) < ('2026-11-09...', 199951)`, new inserts above that timestamp never shift the cursor position.

---

## 4. Why Keyset Cannot Jump Directly to "Page N"

Keyset pagination relies on knowing the `(created_at, id)` boundary values of the last item on Page $N - 1$. Without scanning or maintaining an external rank index, the database does not know which `(created_at, id)` tuple sits at position `(N - 1) * limit`, so arbitrary "Jump to Page 47" buttons are not supported natively.

