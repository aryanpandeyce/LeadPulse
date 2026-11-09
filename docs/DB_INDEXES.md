# Database Indexing Strategy & `EXPLAIN ANALYZE` Benchmarks (Concept 2 & Concept 6)

All indexes are created declaratively via Alembic (`backend/alembic/versions/0001_initial_schema.py`) and SQLAlchemy `__table_args__` (`backend/app/models/entities.py`).

---

## 1. Index Catalog & Rationale

| Table | Index Name | Type | Columns / Expression | Why It Exists |
| :--- | :--- | :--- | :--- | :--- |
| `customers` | `ix_customers_city` | B-Tree | `(city)` | Equality filter `WHERE city = 'Ahmedabad'` on `/customers` |
| `customers` | `ix_customers_status` | B-Tree | `(status)` | Equality filter `WHERE status = 'active'` |
| `customers` | `ix_customers_created_at` | B-Tree | `(created_at)` | Sorting by newest/oldest customer |
| `customers` | `ix_customers_total_purchase_amount` | B-Tree | `(total_purchase_amount)` | Sorting by customer spend (`ORDER BY total_purchase_amount DESC`) |
| `customers` | `ix_customers_status_city_amount` | Composite B-Tree | `(status, city, total_purchase_amount)` | Covers combined filter (`status + city`) + sort by `total_purchase_amount` without an extra sort pass |
| `customers` | `ix_customers_name_email_trgm` | **GIN (`pg_trgm`)** | `((name \|\| ' ' \|\| email) gin_trgm_ops)` | Accelerates substring search `WHERE name ILIKE '%aryan%' OR email ILIKE '%aryan%'` (standard B-Tree cannot accelerate leading wildcard `%...%`) |
| `leads` | `ix_leads_created_at_id_desc` | **Composite B-Tree** | `(created_at DESC, id DESC)` | Powers Concept 6 keyset cursor pagination `WHERE (created_at, id) < (:ts, :id) ORDER BY created_at DESC, id DESC LIMIT 50` in O(1) time |
| `leads` | `ix_leads_created_at_status` | Composite B-Tree | `(created_at, status)` | Accelerates monthly KPI aggregations |
| `monthly_kpis` | `ix_monthly_kpis_month_source` | **Unique B-Tree** | `(month_bucket, source)` | Required by PostgreSQL to run `REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_kpis` without locking concurrent readers |

---

## 2. `EXPLAIN (ANALYZE, BUFFERS)` Before & After Index Creation

> **Measured on**: Windows 10 (AMD64) / PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) / 10,000 customers, 200,000 leads, 500,000 activities / 2026-11-10  
> Raw outputs saved in [`docs/benchmarks/explain_analyze_customers_trgm.txt`](benchmarks/explain_analyze_customers_trgm.txt) and [`docs/benchmarks/explain_analyze_leads_keyset.txt`](benchmarks/explain_analyze_leads_keyset.txt).

### Query A: Substring Search + Sort on 10,000 Customers (`/customers`)
```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, name, email, city, status, total_purchase_amount
FROM customers
WHERE (name || ' ' || email) ILIKE '%aryan%'
ORDER BY total_purchase_amount DESC LIMIT 25;
```

#### BEFORE Index (Sequential Scan — `enable_indexscan=off, enable_bitmapscan=off`)
```text
Limit  (cost=460.01..460.01 rows=1 width=70) (actual time=8.606..8.608 rows=5 loops=1)
  Buffers: shared hit=285
  ->  Sort  (cost=460.01..460.01 rows=1 width=70) (actual time=8.605..8.606 rows=5 loops=1)
        Sort Key: total_purchase_amount DESC
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=285
        ->  Seq Scan on customers  (cost=0.00..460.00 rows=1 width=70) (actual time=0.026..8.511 rows=5 loops=1)
              Filter: ((((name)::text || ' '::text) || (email)::text) ~~* '%aryan%'::text)
              Rows Removed by Filter: 9995
              Buffers: shared hit=285
Planning Time: 8.551 ms
Execution Time: 8.663 ms
```

#### AFTER Index (Bitmap Index Scan using `ix_customers_name_email_trgm` GIN)
```text
Limit  (cost=34.22..34.23 rows=1 width=70) (actual time=0.536..0.537 rows=5 loops=1)
  Buffers: shared hit=8
  ->  Sort  (cost=34.22..34.23 rows=1 width=70) (actual time=0.535..0.535 rows=5 loops=1)
        Sort Key: total_purchase_amount DESC
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=8
        ->  Bitmap Heap Scan on customers  (cost=30.19..34.21 rows=1 width=70) (actual time=0.523..0.528 rows=5 loops=1)
              Recheck Cond: ((((name)::text || ' '::text) || (email)::text) ~~* '%aryan%'::text)
              Heap Blocks: exact=1
              Buffers: shared hit=8
              ->  Bitmap Index Scan on ix_customers_name_email_trgm  (cost=0.00..30.19 rows=1 width=0) (actual time=0.487..0.487 rows=5 loops=1)
                    Index Cond: ((((name)::text || ' '::text) || (email)::text) ~~* '%aryan%'::text)
                    Buffers: shared hit=7
Planning Time: 0.383 ms
Execution Time: 1.010 ms  (8.6x faster execution, 35.6x fewer shared buffer hits: 285 -> 8)
```

---

### Query B: Deep Pagination at Row 150,000 on 200,000 Leads (Concept 6)

#### Deep OFFSET (`OFFSET 150000 LIMIT 50`)
```text
Limit  (cost=10235.48..10238.89 rows=50 width=90) (actual time=83.187..83.261 rows=50 loops=1)
  Buffers: shared hit=3016
  ->  Index Scan using ix_leads_created_at_id_desc on leads  (cost=0.42..13647.17 rows=200000 width=90) (actual time=0.263..78.583 rows=150050 loops=1)
        Buffers: shared hit=3016
Planning Time: 0.315 ms
Execution Time: 83.279 ms
```

#### Keyset Cursor (`WHERE (created_at, id) < (:cursor_ts, :cursor_id) LIMIT 50`)
```text
Limit  (cost=0.42..8.24 rows=50 width=90) (actual time=0.239..0.281 rows=50 loops=1)
  Buffers: shared hit=5
  ->  Index Scan using ix_leads_created_at_id_desc on leads  (cost=0.42..7817.93 rows=49979 width=90) (actual time=0.237..0.275 rows=50 loops=1)
        Index Cond: (ROW(created_at, id) < ROW('2026-07-28 19:19:02.6365+00'::timestamp with time zone, 150605))
        Buffers: shared hit=5
Planning Time: 0.336 ms
Execution Time: 0.330 ms  (252x faster execution at depth 150,000; 603x fewer buffers read: 3,016 -> 5)
```

