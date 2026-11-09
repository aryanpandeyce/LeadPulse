import type { Metadata } from "next";
import "./globals.css";
import { AppProviders } from "@/components/providers";
import { Navbar } from "@/components/navbar";

export const metadata: Metadata = {
  title: "LeadPulse CRM — Production Full-Stack & AI Engineering Portfolio",
  description:
    "Mini CRM with AI Assistant demonstrating 10 core production engineering concepts: Next.js Image optimization, 10k row server-side table, FastAPI async concurrency lab, unified error envelope, Redis + Materialized View caching, keyset pagination on 200k rows, schema-constrained LLM extraction, and LLM cost controls.",
  openGraph: {
    title: "LeadPulse CRM & AI Assistant",
    description: "Production-style full-stack engineering portfolio project.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
        <AppProviders>
          <Navbar />
          <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-6">
            {children}
          </main>
        </AppProviders>
      </body>
    </html>
  );
}

