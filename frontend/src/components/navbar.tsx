"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/dashboard", label: "KPI Dashboard (C5)" },
  { href: "/customers", label: "10k Customers (C2)" },
  { href: "/leads", label: "200k Leads Feed (C6)" },
  { href: "/smart-capture", label: "Smart Capture (C7)" },
  { href: "/ai-assistant", label: "AI Assistant (C8)" },
  { href: "/lab", label: "Async Lab (C3)" },
  { href: "/docs/image-demo", label: "Image Demo (C1)" },
  { href: "/docs/pagination-benchmark", label: "Keyset Bench (C6)" },
  { href: "/admin/ai-costs", label: "AI Costs (C8)" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 text-lg font-bold tracking-tight text-white"
          >
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-blue-600 text-xs font-extrabold text-white">
              LP
            </span>
            <span>LeadPulse</span>
          </Link>
          <span className="hidden rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-medium text-blue-300 sm:inline-block">
            10 Engineering Concepts Live
          </span>
        </div>

        <nav aria-label="Main Navigation" className="flex items-center gap-1 overflow-x-auto py-1">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                  active
                    ? "bg-blue-600 text-white"
                    : "text-slate-300 hover:bg-slate-800/80 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
          <Link
            href="/login"
            className="ml-2 whitespace-nowrap rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800"
          >
            Auth
          </Link>
        </nav>
      </div>
    </header>
  );
}

