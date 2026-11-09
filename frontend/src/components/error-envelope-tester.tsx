"use client";

import React, { useState } from "react";
import { apiFetch, ApiClientError } from "@/lib/api-client";
import { useToast } from "@/components/toast-provider";

const ERROR_KINDS = [
  { kind: "validation", label: "400 ValidationError" },
  { kind: "unauthorized", label: "401 UnauthorizedError" },
  { kind: "forbidden", label: "403 ForbiddenError" },
  { kind: "not_found", label: "404 NotFoundError" },
  { kind: "conflict", label: "409 ConflictError" },
  { kind: "rate_limit", label: "429 RateLimitError" },
  { kind: "external", label: "502 ExternalServiceError" },
  { kind: "unhandled", label: "500 Unhandled Crash (Safe)" },
];

export function ErrorEnvelopeTester() {
  const { showApiErrorToast } = useToast();
  const [lastEnvelope, setLastEnvelope] = useState<string | null>(null);

  async function trigger(kind: string) {
    try {
      await apiFetch(`/error-demo?kind=${kind}`);
    } catch (err) {
      showApiErrorToast(err);
      if (err instanceof ApiClientError) {
        setLastEnvelope(
          JSON.stringify(
            {
              error: {
                code: err.code,
                message: err.message,
                status: err.status,
                request_id: err.requestId,
                details: err.details,
              },
            },
            null,
            2
          )
        );
      }
    }
  }

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
            Concept 4 — Live Interactive Demo
          </span>
          <h2 className="text-base font-bold text-white mt-0.5">
            Unified Error Envelope & Request-ID Correlation Tester
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Click any button to trigger that exception on the FastAPI backend and inspect the normalized JSON envelope + toast notification.
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {ERROR_KINDS.map((item) => (
          <button
            key={item.kind}
            type="button"
            onClick={() => trigger(item.kind)}
            className="rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-blue-500 hover:bg-slate-800"
          >
            {item.label}
          </button>
        ))}
      </div>

      {lastEnvelope && (
        <pre className="mt-4 overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs font-mono text-emerald-300">
          {lastEnvelope}
        </pre>
      )}
    </section>
  );
}

