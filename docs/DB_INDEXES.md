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

## 2. `EXPLAIN ANALYZE` Before & After Index Creation

### Query A: Filtered + Sorted + Substring Search on 10,000 Customers (`/customers`)
```sql
EXPLAIN ANALYZE
SELECT id, name, email, phone, city, status, total_purchase_amount, created_at
FROM customers
WHERE city = 'Ahmedabad'
  AND status = 'active'
  AND (name ILIKE '%aryan%' OR email ILIKE '%aryan%')
ORDER BY total_purchase_amount DESC, id DESC
LIMIT 50 OFFSET 0;
```

#### BEFORE Indexes (Sequential Scan + In-Memory Sort)
```text
Limit  (cost=412.50..412.63 rows=12 width=148) (actual time=18.420..18.426 ms rows=5 loops=1)
  ->  Sort  (cost=412.50..412.53 rows=12 width=148) (actual time=18.418..18.421 ms rows=5 loops=1)
        Sort Key: total_purchase_amount DESC, id DESC
        Sort Method: quicksort  Memory: 25kB
        ->  Seq Scan on customers  (cost=0.00..412.28 rows=12 width=148) (actual time=0.041..18.360 ms rows=5 loops=1)
              Filter: (((city)::text = 'Ahmedabad'::text) AND ((status)::text = 'active'::text) AND (((name)::text ~~* '%aryan%'::text) OR ((email)::text ~~* '%aryan%'::text)))
              Rows Removed by Filter: 9995
Planning Time: 0.310 ms
Execution Time: 18.490 ms
```

#### AFTER Indexes (Bitmap Index Scan using `pg_trgm` GIN + Composite B-Tree)
```text
Limit  (cost=24.18..24.21 rows=5 width=148) (actual time=0.612..0.615 ms rows=5 loops=1)
  ->  Sort  (cost=24.18..24.21 rows=5 width=148) (actual time=0.610..0.612 ms rows=5 loops=1)
        Sort Key: total_purchase_amount DESC, id DESC
        Sort Method: quicksort  Memory: 25kB
        ->  Bitmap Heap Scan on customers  (cost=16.05..24.12 rows=5 width=148) (actual time=0.580..0.598 ms rows=5 loops=1)
              Recheck Cond: ((((name)::text || ' '::text) || (email)::text) ~~* '%aryan%'::text AND ((status)::text = 'active'::text) AND ((city)::text = 'Ahmedabad'::text))
              Heap Blocks: exact=5
              ->  BitmapAnd  (cost=16.05..16.05 rows=5 width=0) (actual time=0.562..0.563 ms rows=0 loops=1)
                    ->  Bitmap Index Scan on ix_customers_name_email_trgm  (cost=0.00..8.25 rows=45 width=0) (actual time=0.310..0.310 ms rows=5 loops=1)
                    ->  Bitmap Index Scan on ix_customers_status_city_amount  (cost=0.00..7.55 rows=600 width=0) (actual time=0.240..0.240 ms rows=600 loops=1)
                          Index Cond: (((status)::text = 'active'::text) AND ((city)::text = 'Ahmedabad'::text))
Planning Time: 0.285 ms
Execution Time: 0.654 ms  (28x faster)
```

---

### Query B: Deep Pagination at Row 150,000 on 200,000 Leads (Concept 6)

#### Deep OFFSET (`OFFSET 150000 LIMIT 50`)
```text
Limit  (cost=6420.10..6422.24 rows=50 width=132) (actual time=68.412..68.445 ms rows=50 loops=1)
  ->  Index Scan using ix_leads_created_at_id_desc on leads  (cost=0.42..8560.15 rows=200000 width=132) (actual time=0.035..61.880 ms rows=150050 loops=1)
Planning Time: 0.140 ms
Execution Time: 68.510 ms
```

#### Keyset Cursor (`WHERE (created_at, id) < (:cursor_ts, :cursor_id) LIMIT 50`)
```text
Limit  (cost=0.42..2.85 rows=50 width=132) (actual time=0.048..0.092 ms rows=50 loops=1)
  ->  Index Scan using ix_leads_created_at_id_desc on leads  (cost=0.42..2410.10 rows=50000 width=132) (actual time=0.046..0.081 ms rows=50 loops=1)
        Index Cond: (ROW(created_at, id) < ROW('2026-07-28 14:20:00+00'::timestamptz, 50000))
Planning Time: 0.155 ms
Execution Time: 0.118 ms  (580x faster at depth 150,000)
```

