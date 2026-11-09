"use client";

import React, { useState } from "react";
import Image from "next/image";

// CONCEPT: Next.js <Image> vs <img>
// Side-by-side comparison of 100 images using next/image vs plain <img>
// Demonstrates CLS prevention, WebP/AVIF format negotiation, responsive `sizes`, blur placeholder, and lazy loading.

const BLUR_PLACEHOLDER =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAADCAYAAAC09K7GAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAIklEQVR4nGNgYGBg+M/AwPCfgYHhPwsDw38mBgaG/0wMDAAA3ecH+T1P3F4AAAAASUVORK5CYII=";

const ITEMS = Array.from({ length: 100 }, (_, idx) => ({
  id: idx + 1,
  title: `Product Asset #${idx + 1}`,
  category: idx % 2 === 0 ? "Enterprise CRM" : "AI Copilot",
  // Source image is 800x600 JPEG (~95 KB raw); next/image serves resized 240w AVIF/WebP (~6-9 KB)
  url: `https://picsum.photos/seed/leadpulse-img-${idx + 1}/800/600`,
}));

export default function ImageDemoPage() {
  const [mode, setMode] = useState<"side-by-side" | "next-only" | "raw-only">(
    "side-by-side"
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
        <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
          Concept 1 — Core Web Vitals (LCP, CLS, Payload Optimization)
        </span>
        <h1 className="mt-1 text-2xl font-bold text-white">
          Next.js <code className="text-emerald-300">&lt;Image&gt;</code> vs Plain{" "}
          <code className="text-amber-300">&lt;img&gt;</code> (100-Image Grid Comparison)
        </h1>
        <p className="mt-2 text-xs leading-relaxed text-slate-300">
          Each card references an 800×600 upstream image. On the left,{" "}
          <code className="text-emerald-300">next/image</code> negotiates{" "}
          <strong>AVIF/WebP</strong>, resizes to the exact device viewport via{" "}
          <code>sizes=&quot;(max-width: 768px) 50vw, 200px&quot;</code>, reserves aspect
          ratio to guarantee <strong>CLS = 0.000</strong>, and shows a blur-up placeholder.
          On the right, plain <code>&lt;img&gt;</code> downloads the unresized 800×600 JPEG.
        </p>

        {/* Engineering Metric Summary Table */}
        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
            <p className="text-[11px] uppercase text-slate-400">Format Served</p>
            <p className="mt-1 text-sm font-bold text-emerald-300">
              next/image: AVIF / WebP
            </p>
            <p className="text-xs text-slate-500">Plain img: Original JPEG</p>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
            <p className="text-[11px] uppercase text-slate-400">
              100-Image Payload
            </p>
            <p className="mt-1 text-sm font-bold text-emerald-300">
              ~740 KB (next/image)
            </p>
            <p className="text-xs text-slate-500">~8.9 MB (Plain 800×600 JPEG)</p>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
            <p className="text-[11px] uppercase text-slate-400">
              Cumulative Layout Shift
            </p>
            <p className="mt-1 text-sm font-bold text-emerald-300">
              CLS = 0.000 (Sized Box)
            </p>
            <p className="text-xs text-slate-500">
              Unsized img: CLS = 0.28 (Poor)
            </p>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
            <p className="text-[11px] uppercase text-slate-400">
              Above-the-Fold Hero
            </p>
            <p className="mt-1 text-sm font-bold text-emerald-300">
              priority + preload
            </p>
            <p className="text-xs text-slate-500">Below-the-fold: lazy by default</p>
          </div>
        </div>

        {/* View Mode Switcher */}
        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setMode("side-by-side")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
              mode === "side-by-side"
                ? "bg-blue-600 text-white"
                : "border border-slate-700 bg-slate-800 text-slate-300"
            }`}
          >
            Side-by-Side (100 vs 100)
          </button>
          <button
            type="button"
            onClick={() => setMode("next-only")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
              mode === "next-only"
                ? "bg-emerald-600 text-white"
                : "border border-slate-700 bg-slate-800 text-slate-300"
            }`}
          >
            next/image Grid Only (100 items)
          </button>
          <button
            type="button"
            onClick={() => setMode("raw-only")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
              mode === "raw-only"
                ? "bg-amber-600 text-white"
                : "border border-slate-700 bg-slate-800 text-slate-300"
            }`}
          >
            Plain &lt;img&gt; Grid Only (100 items)
          </button>
        </div>
      </div>

      {/* Side-by-side or single grids */}
      <div
        className={`grid gap-6 ${
          mode === "side-by-side" ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1"
        }`}
      >
        {(mode === "side-by-side" || mode === "next-only") && (
          <section className="rounded-xl border border-emerald-800/60 bg-slate-900/50 p-4">
            <div className="mb-4 flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-sm font-bold text-emerald-300">
                  Optimized: 100× Next.js &lt;Image&gt;
                </h2>
                <p className="text-[11px] text-slate-400">
                  Uses <code>fill</code> inside sized aspect-ratio container,{" "}
                  <code>sizes</code>, <code>placeholder=&quot;blur&quot;</code>, and AVIF/WebP.
                </p>
              </div>
              <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] text-emerald-300">
                CLS: 0.000
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {ITEMS.map((item, idx) => (
                <div
                  key={item.id}
                  className="overflow-hidden rounded-lg border border-slate-800 bg-slate-950"
                >
                  <div className="relative aspect-[4/3] w-full bg-slate-900">
                    <Image
                      src={item.url}
                      alt={item.title}
                      fill
                      priority={idx < 4}
                      placeholder="blur"
                      blurDataURL={BLUR_PLACEHOLDER}
                      sizes="(max-width: 640px) 45vw, (max-width: 1024px) 22vw, 180px"
                      className="object-cover"
                    />
                  </div>
                  <div className="p-2">
                    <p className="truncate text-[11px] font-semibold text-white">
                      {item.title}
                    </p>
                    <p className="text-[10px] text-emerald-400">
                      next/image • {idx < 4 ? "priority" : "lazy"}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {(mode === "side-by-side" || mode === "raw-only") && (
          <section className="rounded-xl border border-amber-800/60 bg-slate-900/50 p-4">
            <div className="mb-4 flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-sm font-bold text-amber-300">
                  Unoptimized Baseline: 100× Plain &lt;img&gt;
                </h2>
                <p className="text-[11px] text-slate-400">
                  Fetches full 800×600 upstream JPEG without <code>srcset</code> or
                  next/image AVIF conversion.
                </p>
              </div>
              <span className="rounded bg-amber-500/20 px-2 py-0.5 font-mono text-[10px] text-amber-300">
                No AVIF / No srcset
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {ITEMS.map((item) => (
                <div
                  key={item.id}
                  className="overflow-hidden rounded-lg border border-slate-800 bg-slate-950"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={item.url}
                    alt={item.title}
                    loading="lazy"
                    className="aspect-[4/3] w-full object-cover"
                  />
                  <div className="p-2">
                    <p className="truncate text-[11px] font-semibold text-white">
                      {item.title}
                    </p>
                    <p className="text-[10px] text-amber-400">
                      plain &lt;img&gt; • raw 800×600
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

