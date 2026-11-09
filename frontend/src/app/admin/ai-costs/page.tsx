"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiFetch } from "@/lib/api-client";

// CONCEPT: Controlling LLM cost in production (/admin/ai-costs Analytics Dashboard)

interface AiCostDashboardResponse {
  total_requests: number;
  cache_hits: number;
  cache_hit_rate_pct: number;
  total_cost_usd: number;
  estimated_saved_by_cache_and_routing_usd: number;
  cost_by_day: Array<{
    date: string;
    cost_usd: number;
    requests: number;
    cached_requests: number;
  }>;
  cost_by_feature: Array<{
    feature: string;
    requests: number;
    cost_usd: number;
    total_tokens: number;
  }>;
  cost_by_model: Array<{
    model: string;
    requests: number;
    cost_usd: number;
  }>;
  recent_logs: Array<{
    id: number;
    user_id: number | null;
    feature: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    cache_hit: boolean;
    created_at: string;
  }>;
}

export default function AdminAiCostsPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["admin-ai-costs"],
    queryFn: async () => {
      const res = await apiFetch<AiCostDashboardResponse>("/admin/ai-costs");
      return res.data;
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div>
          <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
            Concept 8 — Production LLM FinOps & Usage Observability
          </span>
          <h1 className="mt-1 text-2xl font-bold text-white">
            Admin AI Cost & Cache Efficiency Dashboard
          </h1>
          <p className="mt-1 text-xs text-slate-400">
            Tracks every LLM call in the <code>llm_usage</code> table: daily spend, cache hit rate, model routing distribution, and dollars saved.
          </p>
        </div>

        <button
          type="button"
          onClick={() => refetch()}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
        >
          Refresh Telemetry
        </button>
      </div>

      {isLoading || !data ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-xl border border-slate-800 bg-slate-900/50"
            />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
              <p className="text-[11px] uppercase text-slate-400">
                Total AI Requests
              </p>
              <p className="mt-1 text-2xl font-extrabold text-white">
                {data.total_requests.toLocaleString()}
              </p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
              <p className="text-[11px] uppercase text-slate-400">
                Cache & Short-Circuit Hit Rate
              </p>
              <p className="mt-1 text-2xl font-extrabold text-emerald-400">
                {data.cache_hit_rate_pct}% ({data.cache_hits} hits)
              </p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
              <p className="text-[11px] uppercase text-slate-400">
                Actual Total Spend
              </p>
              <p className="mt-1 text-2xl font-extrabold text-blue-400">
                ${data.total_cost_usd.toFixed(4)}
              </p>
            </div>
            <div className="rounded-xl border border-emerald-800/60 bg-emerald-950/20 p-4">
              <p className="text-[11px] uppercase text-emerald-300">
                Saved by Caching & Model Routing
              </p>
              <p className="mt-1 text-2xl font-extrabold text-emerald-300">
                ${data.estimated_saved_by_cache_and_routing_usd.toFixed(4)}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Daily Requests & Cache Hits Chart */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
              <h2 className="text-sm font-bold text-white">
                Daily AI Requests vs Cache Hits
              </h2>
              <div className="mt-4 h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.cost_by_day}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                    <YAxis stroke="#94a3b8" fontSize={11} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0f172a",
                        borderColor: "#334155",
                        fontSize: "12px",
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: "12px" }} />
                    <Bar
                      dataKey="requests"
                      name="Total Requests"
                      fill="#3b82f6"
                    />
                    <Bar
                      dataKey="cached_requests"
                      name="Cache Hits ($0)"
                      fill="#10b981"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Cost by Feature & Model */}
            <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/50 p-5">
              <h2 className="text-sm font-bold text-white">
                Spend Breakdown by Feature & Model Router
              </h2>
              <div className="space-y-2">
                {data.cost_by_feature.map((f) => (
                  <div
                    key={f.feature}
                    className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs"
                  >
                    <div>
                      <p className="font-bold text-white">{f.feature}</p>
                      <p className="text-[11px] text-slate-400">
                        {f.requests} requests • {f.total_tokens.toLocaleString()}{" "}
                        tokens
                      </p>
                    </div>
                    <span className="font-mono font-bold text-emerald-300">
                      ${f.cost_usd.toFixed(4)}
                    </span>
                  </div>
                ))}
              </div>

              <h3 className="pt-2 text-xs font-bold uppercase text-slate-400">
                By Model Tier (Cheap vs Strong)
              </h3>
              <div className="space-y-2">
                {data.cost_by_model.map((m) => (
                  <div
                    key={m.model}
                    className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs"
                  >
                    <span className="font-mono text-blue-300">{m.model}</span>
                    <span className="text-slate-400">{m.requests} calls</span>
                    <span className="font-mono font-semibold text-emerald-300">
                      ${m.cost_usd.toFixed(4)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
