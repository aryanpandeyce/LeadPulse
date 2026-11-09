"use client";

import React, { useState } from "react";
import Link from "next/link";
import { API_BASE_URL, apiFetch } from "@/lib/api-client";
import { useToast } from "@/components/toast-provider";

// CONCEPT: Controlling LLM cost in production (/ai-assistant with live Debug Telemetry Panel & SSE streaming)

interface AssistantTelemetry {
  route_reason: string;
  chosen_model: string;
  short_circuited: boolean;
  cache_hit: boolean;
  normalized_cache_key: string;
  rag_chunks_used: string[];
  history_turns_kept: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  user_daily_spend_usd: number;
  user_daily_budget_usd: number;
  latency_ms: number;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  telemetry?: AssistantTelemetry;
}

const DEMO_PROMPTS = [
  {
    badge: "Lever #2: Short-Circuit ($0)",
    prompt: "What is your company name?",
  },
  {
    badge: "Lever #1: Cheap Model + RAG-lite",
    prompt: "What are the LeadPulse pricing plans and monthly costs?",
  },
  {
    badge: "Lever #1: Strong Model Router",
    prompt:
      "Compare and analyze the trade-offs between Keyset pagination and Offset pagination in our architecture.",
  },
];

export default function AiAssistantPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState(
    "What are the LeadPulse pricing plans and monthly costs?"
  );
  const [useSseStream, setUseSseStream] = useState(true);
  const [sending, setSending] = useState(false);
  const { showApiErrorToast } = useToast();

  async function sendMessage(promptText: string) {
    if (!promptText.trim()) return;
    const historyPayload = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, { role: "user", content: promptText }]);
    setSending(true);

    try {
      if (useSseStream) {
        // Lever #10: Server-Sent Events (SSE) Streaming
        const resp = await fetch(`${API_BASE_URL}/ai/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: promptText,
            history: historyPayload,
          }),
        });
        if (!resp.ok || !resp.body) {
          throw new Error(`HTTP ${resp.status}`);
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let streamedText = "";
        let finalTelemetry: AssistantTelemetry | undefined;

        setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          for (const line of chunk.split("\n")) {
            if (line.startsWith("data: ")) {
              const event = JSON.parse(line.slice(6));
              if (event.type === "token") {
                streamedText += event.content;
                setMessages((prev) => {
                  const copy = [...prev];
                  copy[copy.length - 1] = {
                    role: "assistant",
                    content: streamedText,
                  };
                  return copy;
                });
              } else if (event.type === "done") {
                finalTelemetry = event.telemetry as AssistantTelemetry;
                setMessages((prev) => {
                  const copy = [...prev];
                  copy[copy.length - 1] = {
                    role: "assistant",
                    content: streamedText.trim(),
                    telemetry: finalTelemetry,
                  };
                  return copy;
                });
              }
            }
          }
        }
      } else {
        const res = await apiFetch<{
          answer: string;
          telemetry: AssistantTelemetry;
        }>("/ai/chat", {
          method: "POST",
          body: JSON.stringify({
            message: promptText,
            history: historyPayload,
          }),
        });
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: res.data.answer,
            telemetry: res.data.telemetry,
          },
        ]);
      }
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSending(false);
    }
  }

  const latestTelemetry = [...messages]
    .reverse()
    .find((m) => m.telemetry)?.telemetry;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div>
          <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
            Concept 8 — Controlling LLM Cost in Production (10 Levers Active)
          </span>
          <h1 className="mt-1 text-2xl font-bold text-white">
            LeadPulse AI Assistant (RAG-Lite + Cost Telemetry)
          </h1>
          <p className="mt-1 text-xs text-slate-400">
            Every message passes through: <strong>1. Short-circuit FAQ</strong> →{" "}
            <strong>2. Model Router (Cheap vs Strong)</strong> →{" "}
            <strong>3. Normalized Redis Cache</strong> →{" "}
            <strong>4. History Trimming (4 turns)</strong> →{" "}
            <strong>5. RAG-lite Top-3 Chunks</strong> →{" "}
            <strong>6. Rate Limit & Daily Spend Cap</strong>.
          </p>
        </div>

        <Link
          href="/admin/ai-costs"
          className="rounded-lg bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-blue-500"
        >
          View Admin AI Cost Dashboard →
        </Link>
      </div>

      {/* Preset Prompt Buttons to Demo Each Lever */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/40 p-3">
        <div className="flex flex-wrap gap-2">
          {DEMO_PROMPTS.map((dp, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setInput(dp.prompt);
                sendMessage(dp.prompt);
              }}
              className="rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-1.5 text-left text-xs hover:border-blue-500"
            >
              <span className="block font-mono text-[10px] text-blue-400">
                {dp.badge}
              </span>
              <span className="text-slate-200">{dp.prompt}</span>
            </button>
          ))}
        </div>

        <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
          <input
            type="checkbox"
            checked={useSseStream}
            onChange={(e) => setUseSseStream(e.target.checked)}
            className="rounded border-slate-700"
          />
          <span>SSE Token Streaming (Feature Flag)</span>
        </label>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Chat Transcript */}
        <div className="flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-900/50 p-4 lg:col-span-7 min-h-[420px]">
          <div className="space-y-4 overflow-y-auto max-h-[360px] pr-1">
            {messages.length === 0 ? (
              <p className="py-12 text-center text-xs text-slate-400">
                Click one of the preset prompts above or ask a question below. Send the same question twice to see the{" "}
                <strong className="text-emerald-300">CACHED</strong> badge!
              </p>
            ) : (
              messages.map((m, idx) => (
                <div
                  key={idx}
                  className={`rounded-xl p-3.5 text-xs ${
                    m.role === "user"
                      ? "ml-8 bg-blue-600/20 border border-blue-500/30 text-white"
                      : "mr-8 bg-slate-950 border border-slate-800 text-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="font-bold uppercase text-[10px] text-slate-400">
                      {m.role}
                    </span>
                    {m.telemetry && (
                      <div className="flex items-center gap-1.5 font-mono text-[10px]">
                        <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-blue-300">
                          {m.telemetry.chosen_model}
                        </span>
                        {m.telemetry.cache_hit && (
                          <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-bold text-emerald-300">
                            {m.telemetry.short_circuited
                              ? "SHORT-CIRCUIT (0 LLM)"
                              : "CACHED (REDIS)"}
                          </span>
                        )}
                        <span className="text-slate-400">
                          ${m.telemetry.cost_usd.toFixed(5)}
                        </span>
                      </div>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap leading-relaxed">
                    {m.content}
                  </p>
                </div>
              ))
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage(input);
            }}
            className="mt-4 flex gap-2 border-t border-slate-800 pt-3"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about pricing, Smart Capture, keyset pagination, or KPI caching..."
              aria-label="Chat message"
              className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-blue-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={sending}
              className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-500 disabled:opacity-50"
            >
              {sending ? "Sending..." : "Send"}
            </button>
          </form>
        </div>

        {/* Live Cost & Routing Debug Panel */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 lg:col-span-5">
          <h2 className="text-sm font-bold text-white">
            Live LLM Cost Control Debug Panel
          </h2>
          <p className="text-xs text-slate-400">
            Real-time telemetry from the latest assistant turn.
          </p>

          {!latestTelemetry ? (
            <p className="mt-8 text-xs text-slate-500">
              Send a message to inspect model routing, RAG chunks, cache key hash, and token budget telemetry.
            </p>
          ) : (
            <dl className="mt-4 space-y-2.5 font-mono text-xs">
              <div className="flex justify-between border-b border-slate-800 pb-1.5">
                <dt className="text-slate-400">1. Chosen Model:</dt>
                <dd className="font-bold text-blue-300">
                  {latestTelemetry.chosen_model}
                </dd>
              </div>
              <div className="border-b border-slate-800 pb-1.5">
                <dt className="text-slate-400">Router Decision:</dt>
                <dd className="mt-0.5 text-[11px] text-slate-200">
                  {latestTelemetry.route_reason}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-1.5">
                <dt className="text-slate-400">2. Short-Circuited:</dt>
                <dd
                  className={
                    latestTelemetry.short_circuited
                      ? "font-bold text-emerald-300"
                      : "text-slate-400"
                  }
                >
                  {String(latestTelemetry.short_circuited)}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-1.5">
                <dt className="text-slate-400">3. Redis Cache Hit:</dt>
                <dd
                  className={
                    latestTelemetry.cache_hit
                      ? "font-bold text-emerald-300"
                      : "text-amber-300"
                  }
                >
                  {latestTelemetry.cache_hit ? "HIT ($0.00)" : "MISS"}
                </dd>
              </div>
              <div className="border-b border-slate-800 pb-1.5">
                <dt className="text-slate-400">Normalized Cache Key:</dt>
                <dd className="mt-0.5 truncate text-[11px] text-slate-300">
                  {latestTelemetry.normalized_cache_key}
                </dd>
              </div>
              <div className="border-b border-slate-800 pb-1.5">
                <dt className="text-slate-400">5. RAG-Lite Top-K Chunks:</dt>
                <dd className="mt-0.5 text-[11px] text-purple-300">
                  {latestTelemetry.rag_chunks_used.length > 0
                    ? latestTelemetry.rag_chunks_used.join(", ")
                    : "none (short-circuited)"}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-1.5">
                <dt className="text-slate-400">7. Tokens (In / Out):</dt>
                <dd className="text-white">
                  {latestTelemetry.input_tokens} / {latestTelemetry.output_tokens}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-1.5">
                <dt className="text-slate-400">Call Cost (USD):</dt>
                <dd className="font-bold text-emerald-300">
                  ${latestTelemetry.cost_usd.toFixed(6)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-400">8. Daily User Budget:</dt>
                <dd className="text-slate-200">
                  ${latestTelemetry.user_daily_spend_usd.toFixed(4)} / $
                  {latestTelemetry.user_daily_budget_usd.toFixed(2)}
                </dd>
              </div>
            </dl>
          )}
        </div>
      </div>
    </div>
  );
}

