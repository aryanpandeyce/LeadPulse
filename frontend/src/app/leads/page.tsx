"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { useToast } from "@/components/toast-provider";

// CONCEPT: Keyset pagination (Infinite scroll activity-feed on 200,000+ leads + Idempotent POST /leads)

interface ActivityItem {
  id: number;
  type: string;
  message: string;
  created_at: string;
}

interface LeadItem {
  id: number;
  customer_id: number | null;
  name: string;
  email: string;
  source: string;
  status: string;
  revenue: string;
  created_at: string;
  activities: ActivityItem[];
}

interface KeysetLeadsResponse {
  data: LeadItem[];
  next_cursor: string | null;
  has_more: boolean;
  query_ms: number;
}

export default function LeadsFeedPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");

  // Quick Idempotent Lead Creation form state
  const [newName, setNewName] = useState("Rohan Mehta");
  const [newEmail, setNewEmail] = useState("rohan.mehta@enterprise.in");
  const [newRevenue, setNewRevenue] = useState("18500");
  const [idempotencyKey, setIdempotencyKey] = useState("idem-demo-key-001");
  const [creating, setCreating] = useState(false);

  const { showToast, showApiErrorToast } = useToast();
  const queryClient = useQueryClient();

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useInfiniteQuery({
    queryKey: ["leads-keyset", statusFilter, sourceFilter],
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams({ limit: "50" });
      if (pageParam) params.set("cursor", pageParam);
      if (statusFilter) params.set("status", statusFilter);
      if (sourceFilter) params.set("source", sourceFilter);
      const res = await apiFetch<KeysetLeadsResponse>(
        `/leads?${params.toString()}`
      );
      return res.data;
    },
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.next_cursor : undefined,
  });

  async function handleCreateIdempotentLead(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await apiFetch<LeadItem>("/leads", {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({
          name: newName,
          email: newEmail,
          source: "linkedin",
          status: "qualified",
          revenue: newRevenue,
          initial_note: "Created via Idempotent Lead Form",
        }),
      });
      showToast({
        title: `Lead #${res.data.id} Saved (Idempotency-Key: ${idempotencyKey})`,
        description:
          "Click 'Submit Lead' again with the same Idempotency-Key to see safe replay without creating duplicates!",
        variant: "success",
      });
      await queryClient.invalidateQueries({ queryKey: ["leads-keyset"] });
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setCreating(false);
    }
  }

  const allLeads = data?.pages.flatMap((p) => p.data) ?? [];
  const latestPage = data?.pages[data.pages.length - 1];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div>
          <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
            Concept 6 — Keyset (Cursor) Pagination on 200,000+ Leads + N+1 Prevention + Idempotency
          </span>
          <h1 className="mt-1 text-2xl font-bold text-white">
            Leads Activity Feed (Keyset Infinite Scroll)
          </h1>
          <p className="mt-1 text-xs text-slate-400">
            Ordered by <code className="text-emerald-300">(created_at DESC, id DESC)</code> with row-value cursor{" "}
            <code className="text-blue-300">WHERE (created_at, id) &lt; (:ts, :id)</code> and eager-loaded activities via{" "}
            <code className="text-purple-300">selectinload(Lead.activities)</code>.
          </p>
        </div>

        <Link
          href="/docs/pagination-benchmark"
          className="rounded-lg bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-blue-500"
        >
          Run Offset vs Keyset Benchmark (Pages 1 → 4000) →
        </Link>
      </div>

      {/* Idempotent POST /leads Demo Bar */}
      <form
        onSubmit={handleCreateIdempotentLead}
        className="rounded-xl border border-slate-800 bg-slate-900/40 p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <p className="text-xs font-bold text-white">
            Idempotent Lead Creation Demo (<code>POST /api/v1/leads</code> with{" "}
            <code className="text-emerald-300">Idempotency-Key</code> header)
          </p>
          <button
            type="button"
            onClick={() =>
              setIdempotencyKey(`idem-${Math.random().toString(36).slice(2, 8)}`)
            }
            className="text-[11px] font-mono text-blue-400 hover:underline"
          >
            Generate New Idempotency-Key
          </button>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Lead Name"
            aria-label="Lead Name"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
          />
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="Lead Email"
            aria-label="Lead Email"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
          />
          <input
            type="number"
            value={newRevenue}
            onChange={(e) => setNewRevenue(e.target.value)}
            placeholder="Revenue ($)"
            aria-label="Lead Revenue"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
          />
          <input
            type="text"
            value={idempotencyKey}
            onChange={(e) => setIdempotencyKey(e.target.value)}
            placeholder="Idempotency-Key"
            aria-label="Idempotency Key"
            className="rounded-lg border border-emerald-700/60 bg-slate-950 px-3 py-1.5 font-mono text-xs text-emerald-300"
          />
          <button
            type="submit"
            disabled={creating}
            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {creating ? "Saving..." : "Submit Lead (Safe Double-Click)"}
          </button>
        </div>
      </form>

      {/* Filters & Cursor Inspector */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/40 p-3 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <select
            aria-label="Filter leads by status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
          >
            <option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="converted">Converted</option>
            <option value="lost">Lost</option>
          </select>

          <select
            aria-label="Filter leads by source"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
          >
            <option value="">All Sources</option>
            <option value="website">Website</option>
            <option value="referral">Referral</option>
            <option value="linkedin">LinkedIn</option>
            <option value="cold_outreach">Cold Outreach</option>
            <option value="event">Event</option>
          </select>

          <span className="text-slate-400">
            Loaded <strong className="text-white">{allLeads.length}</strong> leads across{" "}
            <strong className="text-white">{data?.pages.length ?? 0}</strong> keyset batches
          </span>
        </div>

        <div className="flex items-center gap-2 font-mono text-[11px]">
          {latestPage && (
            <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-emerald-300">
              Last Batch Query: {latestPage.query_ms} ms
            </span>
          )}
          {latestPage?.next_cursor && (
            <span
              title={latestPage.next_cursor}
              className="max-w-xs truncate rounded border border-slate-700 bg-slate-950 px-2 py-0.5 text-slate-400"
            >
              next_cursor: {latestPage.next_cursor}
            </span>
          )}
        </div>
      </div>

      {/* Feed Cards */}
      <div className="space-y-3">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, idx) => (
            <div
              key={idx}
              className="h-20 animate-pulse rounded-xl border border-slate-800 bg-slate-900/50"
            />
          ))
        ) : (
          allLeads.map((lead) => (
            <article
              key={lead.id}
              className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 hover:border-slate-700"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <span className="rounded bg-blue-600/20 px-2 py-0.5 font-mono text-xs font-bold text-blue-300">
                    #{lead.id}
                  </span>
                  <h2 className="text-sm font-bold text-white">{lead.name}</h2>
                  <span className="font-mono text-xs text-slate-400">
                    {lead.email}
                  </span>
                </div>

                <div className="flex items-center gap-2 text-xs">
                  <span className="rounded-full border border-slate-700 bg-slate-800 px-2.5 py-0.5 text-[11px] text-slate-300">
                    {lead.source}
                  </span>
                  <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-medium text-blue-300">
                    {lead.status}
                  </span>
                  <span className="font-mono font-semibold text-emerald-300">
                    ${Number(lead.revenue).toLocaleString()}
                  </span>
                  <span className="font-mono text-[11px] text-slate-500">
                    {new Date(lead.created_at).toISOString()}
                  </span>
                </div>
              </div>

              {lead.activities && lead.activities.length > 0 && (
                <div className="mt-2.5 border-t border-slate-800/80 pt-2 text-xs text-slate-400">
                  <span className="font-mono text-[10px] uppercase text-purple-300 mr-2">
                    [selectinload activity]
                  </span>
                  <span>
                    {lead.activities[0].type.toUpperCase()}: {lead.activities[0].message}
                  </span>
                </div>
              )}
            </article>
          ))
        )}
      </div>

      {/* Load Next Keyset Cursor Button */}
      {hasNextPage && (
        <div className="flex justify-center pt-2">
          <button
            type="button"
            disabled={isFetchingNextPage}
            onClick={() => fetchNextPage()}
            className="rounded-xl bg-blue-600 px-6 py-2.5 text-xs font-bold text-white shadow-lg hover:bg-blue-500 disabled:opacity-50"
          >
            {isFetchingNextPage
              ? "Fetching Next 50 via Keyset Cursor..."
              : "Load Next 50 Leads (Keyset Cursor)"}
          </button>
        </div>
      )}
    </div>
  );
}

