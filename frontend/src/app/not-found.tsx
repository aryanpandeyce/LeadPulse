import Link from "next/link";

// CONCEPT: Error handling & good error design (Custom 404 Not Found boundary)
export default function NotFound() {
  return (
    <div className="mx-auto my-20 max-w-md rounded-xl border border-slate-800 bg-slate-900/60 p-8 text-center">
      <p className="text-xs font-mono uppercase tracking-widest text-blue-400">
        HTTP 404 — NOT_FOUND
      </p>
      <h1 className="mt-2 text-2xl font-bold text-white">Page Not Found</h1>
      <p className="mt-2 text-sm text-slate-400">
        The CRM resource or route you requested does not exist.
      </p>
      <Link
        href="/"
        className="mt-6 inline-block rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500"
      >
        Return to LeadPulse Overview
      </Link>
    </div>
  );
}

