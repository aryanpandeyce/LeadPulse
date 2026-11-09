import Image from "next/image";
import Link from "next/link";
import { ErrorEnvelopeTester } from "@/components/error-envelope-tester";

// Tiny base64 blur placeholder for above-the-fold hero image
const HERO_BLUR_DATA_URL =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAACCAYAAAB/qH1jAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAJ0lEQVR4nGPY2fXjv458/H9Bbtf/IDsD/7+evP8Z2Jn+M/AxAAAmcQ0+74/ruAAAAABJRU5ErkJggg==";

const CONCEPTS = [
  {
    num: 1,
    title: "Next.js <Image> vs <img>",
    desc: "AVIF/WebP negotiation, zero CLS via explicit dimensions, priority hero loading, and 100-image benchmark.",
    href: "/docs/image-demo",
    badge: "/docs/image-demo",
  },
  {
    num: 2,
    title: "10,000 Customers Server Table",
    desc: "Server-side pagination, whitelisted sorting, debounced pg_trgm search, URL query sync, and B-tree/GIN indexes.",
    href: "/customers",
    badge: "/customers",
  },
  {
    num: 3,
    title: "FastAPI async/await Concurrency Lab",
    desc: "asyncio.gather vs event-loop blocking pitfall vs threadpool & ProcessPool CPU offloading + 50-req benchmark.",
    href: "/lab",
    badge: "/lab",
  },
  {
    num: 4,
    title: "Unified Error Envelope & Request-ID",
    desc: "AppError hierarchy, global handlers, X-Request-ID correlation, structured JSON logs, zero leaked internals.",
    href: "#error-demo",
    badge: "Interactive Below",
  },
  {
    num: 5,
    title: "Layered KPI Caching (Redis + MV)",
    desc: "PostgreSQL Materialized View (CONCURRENT refresh) + Redis cache-aside with stampede lock vs raw SQL scan.",
    href: "/dashboard",
    badge: "/dashboard",
  },
  {
    num: 6,
    title: "Keyset (Cursor) vs Offset Pagination",
    desc: "O(1) keyset infinite scroll on 200,000+ leads using row-value comparison vs deep OFFSET slowdown.",
    href: "/leads",
    badge: "/leads & /docs/pagination-benchmark",
  },
  {
    num: 7,
    title: "Reliable Structured JSON from LLMs",
    desc: "Smart Lead Capture with Pydantic JSON schema tool calling, validation retry loop, and defensive fence stripping.",
    href: "/smart-capture",
    badge: "/smart-capture",
  },
  {
    num: 8,
    title: "Controlling LLM Cost in Production",
    desc: "10 cost levers: model router, FAQ short-circuit, normalized Redis cache, RAG-lite, rate limits, daily budgets, SSE.",
    href: "/ai-assistant",
    badge: "/ai-assistant & /admin/ai-costs",
  },
  {
    num: 9,
    title: "Shipping Speed vs Code Quality",
    desc: "Feature flags, conscious tech debt register (TECH_DEBT.md), ROADMAP.md, and non-negotiable guardrails.",
    href: "/admin/ai-costs",
    badge: "docs/TECH_DEBT.md",
  },
  {
    num: 10,
    title: "Maintainable Layered Architecture",
    desc: "Thin routes -> Services -> Repositories, strict mypy + TypeScript (zero any), ADRs, and GitHub Actions CI.",
    href: "/dashboard",
    badge: "ARCHITECTURE.md",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-10">
      {/* Hero Section with next/image priority + blur placeholder (Concept 1) */}
      <section className="grid grid-cols-1 items-center gap-8 rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-blue-950/30 p-6 md:grid-cols-12 md:p-8">
        <div className="space-y-4 md:col-span-7">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-300">
            <span>Production Full-Stack & AI Portfolio</span>
            <span>•</span>
            <span>FastAPI + Next.js 14 + Postgres + Redis</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            LeadPulse CRM & AI Assistant
          </h1>
          <p className="text-sm leading-relaxed text-slate-300">
            Engineered to demonstrate 10 high-signal system design and full-stack concepts on a realistic dataset of{" "}
            <strong className="text-white">10,000 customers</strong>,{" "}
            <strong className="text-white">200,000+ leads</strong>, and{" "}
            <strong className="text-white">500,000 activities</strong>. Every concept is benchmarked, documented, and interactive.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link
              href="/dashboard"
              className="rounded-lg bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white shadow hover:bg-blue-500"
            >
              Open KPI Dashboard (Concept 5)
            </Link>
            <Link
              href="/customers"
              className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-xs font-semibold text-slate-200 hover:bg-slate-800"
            >
              Explore 10k Customers (Concept 2)
            </Link>
            <Link
              href="/smart-capture"
              className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-xs font-semibold text-slate-200 hover:bg-slate-800"
            >
              Try Smart Lead Capture (Concept 7)
            </Link>
          </div>
        </div>

        {/* CONCEPT: Next.js <Image> vs <img> (Hero image with priority, fill, sizes, and blur placeholder) */}
        <div className="relative h-64 w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-900 md:col-span-5">
          <Image
            src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1000&q=80"
            alt="LeadPulse CRM Analytics Dashboard preview"
            fill
            priority
            placeholder="blur"
            blurDataURL={HERO_BLUR_DATA_URL}
            sizes="(max-width: 768px) 100vw, 40vw"
            className="object-cover"
          />
          <div className="absolute bottom-2 right-2 rounded bg-slate-950/85 px-2 py-1 text-[10px] font-mono text-emerald-300 border border-slate-800">
            next/image • priority • AVIF/WebP • 0 CLS
          </div>
        </div>
      </section>

      {/* 10 Engineering Concepts Directory */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">
              The 10 Engineering Concepts (Interactive Map)
            </h2>
            <p className="text-xs text-slate-400">
              Click any card to jump directly to its live UI demonstration and real-time metrics.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CONCEPTS.map((c) => (
            <Link
              key={c.num}
              href={c.href}
              className="group flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-900/60 p-4 transition hover:border-blue-500/60 hover:bg-slate-900"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-blue-600/20 text-xs font-bold text-blue-400">
                    #{c.num}
                  </span>
                  <span className="font-mono text-[11px] text-slate-400 group-hover:text-blue-300">
                    {c.badge}
                  </span>
                </div>
                <h3 className="mt-3 text-sm font-bold text-white group-hover:text-blue-300">
                  {c.title}
                </h3>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
                  {c.desc}
                </p>
              </div>
              <div className="mt-4 text-xs font-semibold text-blue-400 group-hover:underline">
                Open Live Demo →
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Concept 4 Interactive Tester */}
      <div id="error-demo">
        <ErrorEnvelopeTester />
      </div>
    </div>
  );
}

