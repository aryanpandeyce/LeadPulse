"use client";

import React, { useState } from "react";
import { apiFetch } from "@/lib/api-client";
import { useToast } from "@/components/toast-provider";

// CONCEPT: Reliable structured JSON from an LLM (/smart-capture UI)

interface ExtractedLead {
  name: string;
  email: string | null;
  phone: string | null;
  city: string | null;
  interest: string;
  budget: number | null;
  urgency: "low" | "medium" | "high";
  confidence: number;
}

interface SmartCaptureResponse {
  extracted: ExtractedLead;
  model_used: string;
  retries_used: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
}

const SAMPLE_MESSAGES = [
  {
    label: "WhatsApp Urgent Inquiry (Ahmedabad)",
    text: "Hey! I am Vikram Patel from Ahmedabad. Need your Enterprise CRM & AI Copilot urgently this week for 35 reps. Our budget is $18,500. Reach me at vikram.patel@fintechcorp.in or +91-9825012345.",
  },
  {
    label: "Messy Forwarded Email (Bengaluru)",
    text: "Fwd: Hi team, this is Ananya Rao (ananya.rao@cloudscale.io, +91 9900112233) based in Bengaluru. We are exploring LeadPulse Growth plan for next month, budget around $4,200.",
  },
];

export default function SmartCapturePage() {
  const [rawText, setRawText] = useState(SAMPLE_MESSAGES[0].text);
  const [extracting, setExtracting] = useState(false);
  const [meta, setMeta] = useState<Omit<SmartCaptureResponse, "extracted"> | null>(
    null
  );

  // Editable form state populated by LLM structured output
  const [form, setForm] = useState<ExtractedLead>({
    name: "",
    email: "",
    phone: "",
    city: "",
    interest: "",
    budget: null,
    urgency: "medium",
    confidence: 0,
  });
  const [hasExtracted, setHasExtracted] = useState(false);
  const [savingLead, setSavingLead] = useState(false);

  const { showToast, showApiErrorToast } = useToast();

  async function handleExtract(e: React.FormEvent) {
    e.preventDefault();
    setExtracting(true);
    try {
      const res = await apiFetch<SmartCaptureResponse>("/ai/smart-capture", {
        method: "POST",
        body: JSON.stringify({ raw_text: rawText }),
      });
      setForm(res.data.extracted);
      setMeta({
        model_used: res.data.model_used,
        retries_used: res.data.retries_used,
        input_tokens: res.data.input_tokens,
        output_tokens: res.data.output_tokens,
        cost_usd: res.data.cost_usd,
        latency_ms: res.data.latency_ms,
      });
      setHasExtracted(true);
      showToast({
        title: "Structured Lead Extracted via Pydantic Schema",
        description: `Model: ${res.data.model_used} • Confidence: ${Math.round(res.data.extracted.confidence * 100)}% • Retries: ${res.data.retries_used}`,
        variant: "success",
      });
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setExtracting(false);
    }
  }

  async function handleSaveAsLead(e: React.FormEvent) {
    e.preventDefault();
    setSavingLead(true);
    try {
      const res = await apiFetch<{ id: number; name: string }>("/leads", {
        method: "POST",
        headers: {
          "Idempotency-Key": `smart-cap-${form.email || form.name}-${Date.now()}`,
        },
        body: JSON.stringify({
          name: form.name,
          email: form.email || "unknown@prospect.io",
          source: "website",
          status: form.urgency === "high" ? "qualified" : "new",
          revenue: String(form.budget || 0),
          initial_note: `Smart Capture (${form.interest}) | City: ${form.city || "N/A"} | Phone: ${form.phone || "N/A"} | Confidence: ${form.confidence}`,
        }),
      });
      showToast({
        title: `Saved Lead #${res.data.id} (${res.data.name})`,
        description: "Lead added to the 200k+ Leads Feed.",
        variant: "success",
      });
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSavingLead(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
        <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
          Concept 7 — Reliable Structured JSON from an LLM (Tool Calling + Pydantic Validation + Retry Loop)
        </span>
        <h1 className="mt-1 text-2xl font-bold text-white">
          Smart Lead Capture
        </h1>
        <p className="mt-1 text-xs leading-relaxed text-slate-300">
          Paste any unstructured WhatsApp message, email, or call note. The backend passes{" "}
          <code className="text-emerald-300">
            ExtractedLead.model_json_schema()
          </code>{" "}
          to the LLM&apos;s tool-use interface, strips markdown fences defensively, validates with{" "}
          <code className="text-blue-300">model_validate_json()</code>, and retries up to 2 times with validation error feedback if needed.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: Unstructured Input */}
        <form
          onSubmit={handleExtract}
          className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/50 p-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-bold text-white">
              1. Unstructured Message / WhatsApp / Email
            </h2>
            <div className="flex gap-2">
              {SAMPLE_MESSAGES.map((s, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setRawText(s.text)}
                  className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-[11px] text-slate-300 hover:bg-slate-700"
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <textarea
            rows={7}
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            aria-label="Unstructured lead message"
            className="w-full rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-100 focus:border-blue-500 focus:outline-none"
          />

          <button
            type="submit"
            disabled={extracting}
            className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {extracting
              ? "Extracting with Pydantic JSON Schema..."
              : "Extract Structured Lead JSON →"}
          </button>

          {meta && (
            <div className="rounded-lg border border-slate-800 bg-slate-950 p-3 font-mono text-[11px] text-slate-300">
              <p>
                model: <strong className="text-emerald-300">{meta.model_used}</strong> | retries:{" "}
                <strong className="text-blue-300">{meta.retries_used}/2</strong> | latency:{" "}
                <strong>{meta.latency_ms} ms</strong>
              </p>
              <p className="mt-1">
                tokens: {meta.input_tokens} in / {meta.output_tokens} out | est. cost:{" "}
                <strong className="text-emerald-300">${meta.cost_usd.toFixed(6)}</strong>
              </p>
            </div>
          )}
        </form>

        {/* Right: Editable Validated Form */}
        <form
          onSubmit={handleSaveAsLead}
          className="space-y-3 rounded-xl border border-slate-800 bg-slate-900/50 p-5"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white">
              2. Validated <code className="text-emerald-300">ExtractedLead</code> Form (Editable)
            </h2>
            {hasExtracted && (
              <span className="rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-0.5 font-mono text-xs font-bold text-emerald-300">
                Confidence: {Math.round(form.confidence * 100)}%
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-[11px] uppercase text-slate-400">
                Name *
              </label>
              <input
                type="text"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
              />
            </div>

            <div>
              <label className="block text-[11px] uppercase text-slate-400">
                Email (EmailStr)
              </label>
              <input
                type="email"
                value={form.email ?? ""}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
              />
            </div>

            <div>
              <label className="block text-[11px] uppercase text-slate-400">
                Phone / WhatsApp
              </label>
              <input
                type="text"
                value={form.phone ?? ""}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
              />
            </div>

            <div>
              <label className="block text-[11px] uppercase text-slate-400">
                City
              </label>
              <input
                type="text"
                value={form.city ?? ""}
                onChange={(e) => setForm({ ...form, city: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
              />
            </div>

            <div>
              <label className="block text-[11px] uppercase text-slate-400">
                Budget (USD)
              </label>
              <input
                type="number"
                value={form.budget ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    budget: e.target.value ? Number(e.target.value) : null,
                  })
                }
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
              />
            </div>

            <div>
              <label className="block text-[11px] uppercase text-slate-400">
                Urgency (Enum)
              </label>
              <select
                value={form.urgency}
                onChange={(e) =>
                  setForm({
                    ...form,
                    urgency: e.target.value as "low" | "medium" | "high",
                  })
                }
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
              >
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[11px] uppercase text-slate-400">
              Product / Service Interest
            </label>
            <input
              type="text"
              value={form.interest}
              onChange={(e) => setForm({ ...form, interest: e.target.value })}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
            />
          </div>

          <button
            type="submit"
            disabled={!hasExtracted || savingLead}
            className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-emerald-500 disabled:opacity-40"
          >
            {savingLead
              ? "Saving to Leads Table..."
              : "Confirm & Save Validated Lead to CRM"}
          </button>
        </form>
      </div>
    </div>
  );
}
