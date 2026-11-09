"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { useToast } from "@/components/toast-provider";
import type {
  LeadsBySourceItem,
  MonthlyTrendPoint,
} from "@/components/kpi-charts";

// Dynamic import for heavy Recharts visualization (Next.js bundle optimization)
const KpiCharts = dynamic(() => import("@/components/kpi-charts"), {
  ssr: false,
  loading: () => (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="h-80 animate-pulse rounded-xl border border-slate-800 bg-slate-900/50" />
      <div className="h-80 animate-pulse rounded-xl border border-slate-800 bg-slate-900/50" />
    </div>
  ),
});

interface DashboardKpiResponse {
  source: "redis" | "materialized_view" | "raw";
  query_ms: number;
  cache_key_version: number;
  total_leads: number;
  converted_leads: number;
  lost_leads: number;
  total_revenue: number;
  conversion_rate_pct: number;
  leads_by_source: LeadsBySourceItem[];
  monthly_trend: MonthlyTrendPoint[];
}

export default function DashboardPage() {
  const [pathMode, setPathMode] = useState<"layered" | "mv_only" | "raw">(
    "layered"
  );
  const [refreshingMv, setRefreshingMv] = useState(false);
  const { showToast, showApiErrorToast } = useToast();
  const queryClient = useQueryClient();

  const endpoint =
    pathMode === "raw"
      ? "/kpis/raw"
      : pathMode === "mv_only"
        ? "/kpis?bypass_redis=true"
        : "/kpis";

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["dashboard-kpis", pathMode],
    queryFn: async () => {
      const res = await apiFetch<DashboardKpiResponse>(endpoint);
      return res.data;
    },
  });

  async function handleAdminRefreshView() {
    setRefreshingMv(true);
    try {
      const res = await apiFetch<{
        status: string;
        refreshed_view: string;
        new_cache_version: number;
        elapsed_ms: number;
      }>("/admin/kpis/refresh", { method: "POST" });

      showToast({
        title: `Refreshed ${res.data.refreshed_view} (${res.data.elapsed_ms} ms)`,
        description: `Redis cache invalidated -> new version v${res.data.new_cache_version}`,
        variant: "success",
      });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-kpis"] });
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setRefreshingMv(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header & Source Debug Badge */}
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div>
          <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
            Concept 5 — Two-Layer Caching (Redis Cache-Aside + PostgreSQL Materialized View vs Raw SQL)
          </span>
          <h1 className="mt-1 text-2xl font-bold text-white">
            Executive Revenue & Pipeline KPI Dashboard
          </h1>
          <p className="mt-1 text-xs text-slate-400">
            Switch between <strong>Redis Cache-Aside</strong>,{" "}
            <strong>Materialized View (<code>monthly_kpis</code>)</strong>, and{" "}
            <strong>Slow-Path Raw Aggregation</strong> to compare query latency in real time.
          </p>
        </div>

        {/* CONCEPT: Caching an expensive aggregate (Debug badge showing source + query_ms) */}
        <div className="flex flex-wrap items-center gap-3">
          {data && (
            <div
              className={`flex items-center gap-2 rounded-xl border px-3.5 py-2 font-mono text-xs ${
                data.source === "redis"
                  ? "border-emerald-500/40 bg-emerald-950/60 text-emerald-300"
                  : data.source === "materialized_view"
                    ? "border-blue-500/40 bg-blue-950/60 text-blue-300"
                    : "border-amber-500/40 bg-amber-950/60 text-amber-300"
              }`}
            >
              <span className="h-2 w-2 rounded-full bg-current" />
              <span>
                source = <strong>&quot;{data.source}&quot;</strong>
              </span>
              <span>•</span>
              <span>
                <strong>{data.query_ms} ms</strong>
              </span>
              <span>•</span>
              <span>v{data.cache_key_version}</span>
            </div>
          )}

          <button
            type="button"
            onClick={handleAdminRefreshView}
            disabled={refreshingMv}
            className="rounded-lg border border-purple-500/40 bg-purple-950/50 px-3 py-2 text-xs font-semibold text-purple-200 hover:bg-purple-900/50 disabled:opacity-50"
          >
            {refreshingMv
              ? "Refreshing MV..."
              : "Admin: Refresh MV + Invalidate Redis"}
          </button>
        </div>
      </div>

      {/* Layer Switcher Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/40 p-3">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setPathMode("layered")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
              pathMode === "layered"
                ? "bg-emerald-600 text-white"
                : "border border-slate-700 bg-slate-800 text-slate-300"
            }`}
          >
            1. Fast Path: Redis Cache-Aside (~0.4 ms)
          </button>
          <button
            type="button"
            onClick={() => setPathMode("mv_only")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
              pathMode === "mv_only"
                ? "bg-blue-600 text-white"
                : "border border-slate-700 bg-slate-800 text-slate-300"
            }`}
          >
            2. Middle Layer: Materialized View (~2.5 ms)
          </button>
          <button
            type="button"
            onClick={() => setPathMode("raw")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
              pathMode === "raw"
                ? "bg-amber-600 text-white"
                : "border border-slate-700 bg-slate-800 text-slate-300"
            }`}
          >
            3. Slow Path: Raw 200k Leads Scan (~85 ms)
          </button>
        </div>

        <button
          type="button"
          onClick={() => refetch()}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
        >
          {isFetching ? "Measuring..." : "Re-run Query & Measure Latency"}
        </button>
      </div>

      {/* Top KPI Cards */}
      {isLoading || !data ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-xl border border-slate-800 bg-slate-900/50"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
            <p className="text-[11px] uppercase text-slate-400">Total Leads</p>
            <p className="mt-1 text-2xl font-extrabold text-white">
              {data.total_leads.toLocaleString()}
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
            <p className="text-[11px] uppercase text-slate-400">
              Converted Leads
            </p>
            <p className="mt-1 text-2xl font-extrabold text-emerald-400">
              {data.converted_leads.toLocaleString()}
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
            <p className="text-[11px] uppercase text-slate-400">Lost Leads</p>
            <p className="mt-1 text-2xl font-extrabold text-red-400">
              {data.lost_leads.toLocaleString()}
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
            <p className="text-[11px] uppercase text-slate-400">
              Conversion Rate
            </p>
            <p className="mt-1 text-2xl font-extrabold text-blue-400">
              {data.conversion_rate_pct}%
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
            <p className="text-[11px] uppercase text-slate-400">Total Revenue</p>
            <p className="mt-1 text-2xl font-extrabold text-emerald-300">
              ${data.total_revenue.toLocaleString()}
            </p>
          </div>
        </div>
      )}

      {/* Charts */}
      {data && (
        <KpiCharts
          monthlyTrend={data.monthly_trend}
          leadsBySource={data.leads_by_source}
        />
      )}
    </div>
  );
}

