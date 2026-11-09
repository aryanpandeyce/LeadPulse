"use client";

import React, { Suspense, useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { API_BASE_URL, apiFetch } from "@/lib/api-client";
import { useDebounce } from "@/hooks/use-debounce";

// CONCEPT: Paginated, sortable, filterable table of 10,000 customers
// State lives in the URL query string (?page=1&limit=50&sort_by=name&order=asc&city=Ahmedabad&status=active&q=aryan)
// Search input is debounced 300ms; uses TanStack Query with placeholderData: keepPreviousData

export interface CustomerRow {
  id: number;
  name: string;
  email: string;
  phone: string;
  city: string;
  status: "active" | "inactive" | "churned";
  total_purchase_amount: string;
  avatar_url: string;
  company_logo_url: string;
  created_at: string;
}

export interface PaginatedCustomersResponse {
  data: CustomerRow[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  query_ms: number;
}

const CITIES = [
  "",
  "Ahmedabad",
  "Bengaluru",
  "Mumbai",
  "Delhi",
  "Pune",
  "Hyderabad",
  "Chennai",
  "Kolkata",
  "Surat",
  "Jaipur",
];

const SORTABLE_COLUMNS: Array<{ key: string; label: string }> = [
  { key: "name", label: "Customer" },
  { key: "email", label: "Email" },
  { key: "city", label: "City" },
  { key: "status", label: "Status" },
  { key: "total_purchase_amount", label: "Total Spend ($)" },
  { key: "created_at", label: "Created At" },
];

function CustomersTableInner() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const page = Number(searchParams.get("page") || "1");
  const limit = Number(searchParams.get("limit") || "50");
  const sortBy = searchParams.get("sort_by") || "name";
  const order = (searchParams.get("order") || "asc") as "asc" | "desc";
  const city = searchParams.get("city") || "";
  const status = searchParams.get("status") || "";
  const urlQuery = searchParams.get("q") || "";

  const [searchInput, setSearchInput] = useState(urlQuery);
  const debouncedSearch = useDebounce(searchInput, 300);

  const updateUrlParams = useCallback(
    (updates: Record<string, string | number | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [k, v] of Object.entries(updates)) {
        if (v === null || v === "") {
          params.delete(k);
        } else {
          params.set(k, String(v));
        }
      }
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams]
  );

  // Sync debounced search input to URL query parameter
  useEffect(() => {
    if (debouncedSearch !== urlQuery) {
      updateUrlParams({ q: debouncedSearch || null, page: 1 });
    }
  }, [debouncedSearch, urlQuery, updateUrlParams]);

  const queryString = new URLSearchParams({
    page: String(page),
    limit: String(limit),
    sort_by: sortBy,
    order,
    ...(city ? { city } : {}),
    ...(status ? { status } : {}),
    ...(urlQuery ? { q: urlQuery } : {}),
  }).toString();

  const { data, isLoading, isFetching, isError, error } = useQuery({
    queryKey: ["customers", page, limit, sortBy, order, city, status, urlQuery],
    queryFn: async () => {
      const res = await apiFetch<PaginatedCustomersResponse>(
        `/customers?${queryString}`
      );
      return res.data;
    },
    placeholderData: keepPreviousData,
  });

  function toggleSort(colKey: string) {
    if (sortBy === colKey) {
      updateUrlParams({ order: order === "asc" ? "desc" : "asc", page: 1 });
    } else {
      updateUrlParams({ sort_by: colKey, order: "asc", page: 1 });
    }
  }

  function applyPresetAhmedabadAryan() {
    setSearchInput("aryan");
    updateUrlParams({
      page: 1,
      limit: 50,
      sort_by: "name",
      order: "asc",
      city: "Ahmedabad",
      status: "active",
      q: "aryan",
    });
  }

  return (
    <div className="space-y-6">
      {/* Header & Concept Banner */}
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div>
          <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
            Concept 2 — Server-Side Pagination, Whitelisted Sort & pg_trgm Search
          </span>
          <h1 className="mt-1 text-2xl font-bold text-white">
            10,000 Customers Directory
          </h1>
          <p className="mt-1 text-xs text-slate-400">
            URL-synced state • 300ms debounced search • B-tree + composite + pg_trgm GIN indexes • TanStack Query{" "}
            <code className="text-blue-300">keepPreviousData</code> •{" "}
            <code className="text-emerald-300">next/image</code> avatars & company logos.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={applyPresetAhmedabadAryan}
            className="rounded-lg border border-blue-500/40 bg-blue-950/50 px-3 py-1.5 text-xs font-semibold text-blue-300 hover:bg-blue-900/50"
          >
            Demo Query: city=Ahmedabad & status=active & q=aryan
          </button>
          <a
            href={`${API_BASE_URL}/customers/export.csv?${queryString}`}
            className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
          >
            Stream CSV Export
          </a>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="grid grid-cols-1 gap-3 rounded-xl border border-slate-800 bg-slate-900/40 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <label
            htmlFor="customer-search"
            className="block text-[11px] font-medium uppercase text-slate-400"
          >
            Search Name or Email (300ms Debounced • pg_trgm GIN)
          </label>
          <input
            id="customer-search"
            type="search"
            placeholder="e.g. aryan or customer.42..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-blue-500 focus:outline-none"
          />
        </div>

        <div>
          <label
            htmlFor="customer-city"
            className="block text-[11px] font-medium uppercase text-slate-400"
          >
            City (B-tree Index)
          </label>
          <select
            id="customer-city"
            value={city}
            onChange={(e) => updateUrlParams({ city: e.target.value || null, page: 1 })}
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-blue-500 focus:outline-none"
          >
            <option value="">All Cities</option>
            {CITIES.filter(Boolean).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="customer-status"
            className="block text-[11px] font-medium uppercase text-slate-400"
          >
            Status (B-tree Index)
          </label>
          <select
            id="customer-status"
            value={status}
            onChange={(e) =>
              updateUrlParams({ status: e.target.value || null, page: 1 })
            }
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-blue-500 focus:outline-none"
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="churned">Churned</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="customer-limit"
            className="block text-[11px] font-medium uppercase text-slate-400"
          >
            Rows Per Page (Max 100)
          </label>
          <select
            id="customer-limit"
            value={limit}
            onChange={(e) =>
              updateUrlParams({ limit: Number(e.target.value), page: 1 })
            }
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-blue-500 focus:outline-none"
          >
            <option value={25}>25 rows</option>
            <option value={50}>50 rows</option>
            <option value={100}>100 rows (max)</option>
          </select>
        </div>
      </div>

      {/* Live Telemetry Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
        <div className="flex items-center gap-3">
          <span>
            Showing{" "}
            <strong className="text-white">{data?.data.length ?? 0}</strong> of{" "}
            <strong className="text-white">
              {data?.total.toLocaleString() ?? "—"}
            </strong>{" "}
            matching customers
          </span>
          {data?.query_ms !== undefined && (
            <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[11px] text-emerald-300">
              DB Query: {data.query_ms} ms
            </span>
          )}
          {isFetching && (
            <span className="font-mono text-[11px] text-blue-400 animate-pulse">
              Refreshing...
            </span>
          )}
        </div>
        <div className="font-mono text-[11px] text-slate-500">
          GET /api/v1/customers?{queryString}
        </div>
      </div>

      {/* Error State */}
      {isError && (
        <div className="rounded-xl border border-red-800 bg-red-950/40 p-6 text-center">
          <p className="text-sm font-semibold text-red-200">
            Failed to load customers
          </p>
          <p className="mt-1 text-xs text-red-300">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </div>
      )}

      {/* Table or Loading Skeletons */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/50">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-slate-800 bg-slate-950/70 text-[11px] uppercase text-slate-400">
            <tr>
              {SORTABLE_COLUMNS.map((col) => {
                const isSorted = sortBy === col.key;
                return (
                  <th key={col.key} className="px-4 py-3 font-semibold">
                    <button
                      type="button"
                      onClick={() => toggleSort(col.key)}
                      className="inline-flex items-center gap-1 hover:text-white"
                    >
                      <span>{col.label}</span>
                      {isSorted ? (
                        <span className="text-blue-400">
                          {order === "asc" ? "▲" : "▼"}
                        </span>
                      ) : (
                        <span className="opacity-30">↕</span>
                      )}
                    </button>
                  </th>
                );
              })}
              <th className="px-4 py-3 font-semibold">Company</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {isLoading ? (
              Array.from({ length: 10 }).map((_, idx) => (
                <tr key={idx} className="animate-pulse">
                  <td className="px-4 py-3" colSpan={7}>
                    <div className="h-6 w-full rounded bg-slate-800/70" />
                  </td>
                </tr>
              ))
            ) : data && data.data.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                  No customers matched your filter criteria. Try clearing filters.
                </td>
              </tr>
            ) : (
              data?.data.map((cust) => (
                <tr
                  key={cust.id}
                  className="hover:bg-slate-800/40 transition-colors"
                >
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2.5">
                      {/* CONCEPT: Next.js <Image> vs <img> (Customer Avatar with explicit width/height) */}
                      <Image
                        src={cust.avatar_url}
                        alt={`${cust.name} avatar`}
                        width={32}
                        height={32}
                        className="h-8 w-8 rounded-full object-cover border border-slate-700"
                      />
                      <div>
                        <p className="font-semibold text-white">{cust.name}</p>
                        <p className="text-[11px] text-slate-400">{cust.phone}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-slate-300">
                    {cust.email}
                  </td>
                  <td className="px-4 py-2.5 text-slate-200">{cust.city}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        cust.status === "active"
                          ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                          : cust.status === "inactive"
                            ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                            : "bg-red-500/15 text-red-300 border border-red-500/30"
                      }`}
                    >
                      {cust.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono font-semibold text-emerald-300">
                    ${Number(cust.total_purchase_amount).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-slate-400">
                    {new Date(cust.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2.5">
                    {/* CONCEPT: Next.js <Image> vs <img> (Company Logo with explicit width/height) */}
                    <Image
                      src={cust.company_logo_url}
                      alt={`${cust.name} company logo`}
                      width={28}
                      height={28}
                      className="h-7 w-7 rounded-md object-cover border border-slate-700"
                    />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {data && data.total_pages > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3 text-xs">
          <div>
            Page <strong className="text-white">{data.page}</strong> of{" "}
            <strong className="text-white">{data.total_pages}</strong>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => updateUrlParams({ page: 1 })}
              className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 disabled:opacity-40"
            >
              First
            </button>
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => updateUrlParams({ page: page - 1 })}
              className="rounded border border-slate-700 bg-slate-800 px-3 py-1 disabled:opacity-40"
            >
              ← Prev
            </button>
            <button
              type="button"
              disabled={page >= data.total_pages}
              onClick={() => updateUrlParams({ page: page + 1 })}
              className="rounded border border-slate-700 bg-slate-800 px-3 py-1 disabled:opacity-40"
            >
              Next →
            </button>
            <button
              type="button"
              disabled={page >= data.total_pages}
              onClick={() => updateUrlParams({ page: data.total_pages })}
              className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 disabled:opacity-40"
            >
              Last
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CustomersPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-sm text-slate-400">
          Loading 10k Customers Directory...
        </div>
      }
    >
      <CustomersTableInner />
    </Suspense>
  );
}
