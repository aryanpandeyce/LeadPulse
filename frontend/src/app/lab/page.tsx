"use client";

import React, { useState } from "react";
import { apiFetch } from "@/lib/api-client";
import { useToast } from "@/components/toast-provider";

// CONCEPT: async/await in FastAPI (Interactive Concurrency Lab UI)

interface LabIoResponse {
  mode: string;
  simulated_calls: number;
  per_call_delay_ms: number;
  elapsed_ms: number;
  explanation: string;
}

interface CpuJobStatus {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  rows_processed: number;
  checksum: string | null;
  elapsed_ms: number | null;
  worker_type: string;
}

export default function ConcurrencyLabPage() {
  const [burstSize, setBurstSize] = useState(15);
  const [delayMs, setDelayMs] = useState(50);
  const [runningMode, setRunningMode] = useState<string | null>(null);
  const [results, setResults] = useState<
    Array<{
      label: string;
      mode: string;
      wallTimeMs: number;
      avgLatencyMs: number;
      explanation: string;
    }>
  >([]);

  const [cpuJob, setCpuJob] = useState<CpuJobStatus | null>(null);
  const [submittingCpu, setSubmittingCpu] = useState(false);
  const { showApiErrorToast } = useToast();

  async function fireConcurrentBurst(
    label: string,
    endpoint: string,
    modeKey: string
  ) {
    setRunningMode(modeKey);
    try {
      const t0 = performance.now();
      const responses = await Promise.all(
        Array.from({ length: burstSize }, () =>
          apiFetch<LabIoResponse>(`${endpoint}?delay_ms=${delayMs}`)
        )
      );
      const wallTimeMs = Math.round(performance.now() - t0);
      const avgLatencyMs = Math.round(
        responses.reduce((acc, r) => acc + r.data.elapsed_ms, 0) /
          responses.length
      );
      setResults((prev) => [
        {
          label,
          mode: modeKey,
          wallTimeMs,
          avgLatencyMs,
          explanation: responses[0].data.explanation,
        },
        ...prev,
      ]);
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setRunningMode(null);
    }
  }

  async function triggerCpuHeavyJob() {
    setSubmittingCpu(true);
    try {
      const res = await apiFetch<CpuJobStatus>("/lab/cpu-heavy", {
        method: "POST",
        body: JSON.stringify({ rows_to_process: 75000 }),
      });
      setCpuJob(res.data);

      // Poll until completed
      const jobId = res.data.job_id;
      for (let i = 0; i < 15; i++) {
        await new Promise((r) => setTimeout(r, 250));
        const poll = await apiFetch<CpuJobStatus>(`/lab/jobs/${jobId}`);
        setCpuJob(poll.data);
        if (
          poll.data.status === "completed" ||
          poll.data.status === "failed"
        ) {
          break;
        }
      }
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSubmittingCpu(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
        <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
          Concept 3 — When async/await Helps (I/O) vs When It Hurts (Event Loop Blocking & CPU)
        </span>
        <h1 className="mt-1 text-2xl font-bold text-white">
          FastAPI Concurrency Lab
        </h1>
        <p className="mt-1 text-xs leading-relaxed text-slate-300">
          Fire a burst of concurrent requests from your browser at each endpoint to see how{" "}
          <code className="text-emerald-300">asyncio.gather</code> and{" "}
          <code className="text-blue-300">run_in_threadpool</code> keep the event loop non-blocking, while calling synchronous{" "}
          <code className="text-red-300">time.sleep()</code> inside{" "}
          <code>async def</code> serializes every request.
        </p>

        {/* Controls */}
        <div className="mt-5 flex flex-wrap items-end gap-4">
          <div>
            <label
              htmlFor="burst-size"
              className="block text-[11px] uppercase text-slate-400"
            >
              Concurrent Burst Size
            </label>
            <select
              id="burst-size"
              value={burstSize}
              onChange={(e) => setBurstSize(Number(e.target.value))}
              className="mt-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
            >
              <option value={10}>10 Concurrent Requests</option>
              <option value={15}>15 Concurrent Requests</option>
              <option value={25}>25 Concurrent Requests</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="delay-ms"
              className="block text-[11px] uppercase text-slate-400"
            >
              Simulated I/O Delay per Call
            </label>
            <select
              id="delay-ms"
              value={delayMs}
              onChange={(e) => setDelayMs(Number(e.target.value))}
              className="mt-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
            >
              <option value={30}>30 ms</option>
              <option value={50}>50 ms</option>
              <option value={100}>100 ms</option>
            </select>
          </div>

          <button
            type="button"
            disabled={runningMode !== null}
            onClick={() =>
              fireConcurrentBurst(
                "1. GET /lab/io-async (3x I/O via asyncio.gather)",
                "/lab/io-async",
                "async"
              )
            }
            className="rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {runningMode === "async"
              ? "Running..."
              : `Fire ${burstSize}x at /lab/io-async (FAST)`}
          </button>

          <button
            type="button"
            disabled={runningMode !== null}
            onClick={() =>
              fireConcurrentBurst(
                "2. GET /lab/io-blocking-right (run_in_threadpool)",
                "/lab/io-blocking-right",
                "right"
              )
            }
            className="rounded-lg bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {runningMode === "right"
              ? "Running..."
              : `Fire ${burstSize}x at /lab/io-blocking-right (THREADPOOL)`}
          </button>

          <button
            type="button"
            disabled={runningMode !== null}
            onClick={() =>
              fireConcurrentBurst(
                "3. GET /lab/io-blocking-wrong (BLOCKS EVENT LOOP!)",
                "/lab/io-blocking-wrong",
                "wrong"
              )
            }
            className="rounded-lg bg-red-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-red-500 disabled:opacity-50"
          >
            {runningMode === "wrong"
              ? "Blocking Event Loop..."
              : `Fire ${burstSize}x at /lab/io-blocking-wrong (WRONG)`}
          </button>
        </div>
      </div>

      {/* Live Burst Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-bold text-white">
            Live Browser Burst Telemetry
          </h2>
          {results.map((r, i) => (
            <div
              key={i}
              className={`rounded-xl border p-4 ${
                r.mode === "wrong"
                  ? "border-red-800/70 bg-red-950/30"
                  : r.mode === "async"
                    ? "border-emerald-800/70 bg-emerald-950/30"
                    : "border-blue-800/70 bg-blue-950/30"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-bold text-white">{r.label}</p>
                <span className="rounded bg-slate-950 px-3 py-1 font-mono text-xs font-bold text-emerald-300">
                  Total Wall Time ({burstSize} reqs): {r.wallTimeMs} ms
                </span>
              </div>
              <p className="mt-1.5 text-xs text-slate-300">{r.explanation}</p>
            </div>
          ))}
        </div>
      )}

      {/* CPU-Heavy ProcessPoolExecutor Offloading Card */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="text-xs font-mono uppercase text-purple-400">
              CPU-Bound Offloading (ProcessPoolExecutor + Polling)
            </span>
            <h2 className="mt-0.5 text-base font-bold text-white">
              POST /api/v1/lab/cpu-heavy → GET /api/v1/lab/jobs/&#123;id&#125;
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              CPU-heavy tasks (cryptographic digest / 75,000-row report generation) hold the Python GIL. We offload them to a{" "}
              <code>ProcessPoolExecutor</code> and immediately return a <code>job_id</code> (HTTP 202).
            </p>
          </div>
          <button
            type="button"
            disabled={submittingCpu}
            onClick={triggerCpuHeavyJob}
            className="rounded-lg bg-purple-600 px-4 py-2 text-xs font-semibold text-white hover:bg-purple-500 disabled:opacity-50"
          >
            {submittingCpu
              ? "Running in Worker Process..."
              : "Start 75,000-Row CPU Report Job"}
          </button>
        </div>

        {cpuJob && (
          <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-xs">
            <p className="text-slate-300">
              job_id: <strong className="text-white">{cpuJob.job_id}</strong> | status:{" "}
              <strong className="text-emerald-400">{cpuJob.status}</strong> | worker:{" "}
              <span className="text-purple-300">{cpuJob.worker_type}</span>
            </p>
            {cpuJob.checksum && (
              <p className="mt-1 text-emerald-300">
                SHA-256 Checksum: {cpuJob.checksum} • Computed {cpuJob.rows_processed.toLocaleString()} rows in {cpuJob.elapsed_ms} ms without blocking FastAPI!
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

