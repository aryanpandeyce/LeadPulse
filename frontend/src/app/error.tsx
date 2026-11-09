"use client";

import React from "react";

// CONCEPT: Error handling & good error design (Next.js App Router Error Boundary)
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto my-16 max-w-lg rounded-xl border border-red-800/70 bg-red-950/30 p-6 text-center">
      <div className="mx-auto mb-3 inline-flex h-10 w-10 items-center justify-center rounded-full bg-red-900/50 text-red-300 font-bold">
        !
      </div>
      <h2 className="text-lg font-bold text-white">Something went wrong</h2>
      <p className="mt-2 text-sm text-slate-300">
        {error.message || "An unexpected client or server rendering error occurred."}
      </p>
      {error.digest && (
        <p className="mt-2 font-mono text-xs text-slate-400">
          Digest: {error.digest}
        </p>
      )}
      <div className="mt-5 flex justify-center gap-3">
        <button
          type="button"
          onClick={() => reset()}
          className="rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-500"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}

