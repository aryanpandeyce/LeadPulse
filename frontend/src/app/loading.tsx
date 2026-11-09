export default function Loading() {
  return (
    <div className="space-y-4 py-8" aria-busy="true" aria-label="Loading page content">
      <div className="h-8 w-64 animate-pulse rounded-lg bg-slate-800" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="h-28 animate-pulse rounded-xl bg-slate-900 border border-slate-800" />
        <div className="h-28 animate-pulse rounded-xl bg-slate-900 border border-slate-800" />
        <div className="h-28 animate-pulse rounded-xl bg-slate-900 border border-slate-800" />
      </div>
      <div className="h-64 animate-pulse rounded-xl bg-slate-900 border border-slate-800" />
    </div>
  );
}

