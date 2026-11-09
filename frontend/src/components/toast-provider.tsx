"use client";

import React, { createContext, useCallback, useContext, useState } from "react";
import { ApiClientError } from "@/lib/api-client";

export interface ToastMessage {
  id: string;
  title: string;
  description: string;
  code?: string;
  requestId?: string;
  variant: "info" | "success" | "error";
}

interface ToastContextValue {
  toasts: ToastMessage[];
  showToast: (toast: Omit<ToastMessage, "id">) => void;
  showApiErrorToast: (err: unknown) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (toast: Omit<ToastMessage, "id">) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => [...prev, { ...toast, id }]);
      setTimeout(() => {
        dismissToast(id);
      }, 6000);
    },
    [dismissToast]
  );

  const showApiErrorToast = useCallback(
    (err: unknown) => {
      if (err instanceof ApiClientError) {
        showToast({
          title: `${err.code} (HTTP ${err.status})`,
          description: err.message,
          code: err.code,
          requestId: err.requestId,
          variant: "error",
        });
      } else if (err instanceof Error) {
        showToast({
          title: "Application Error",
          description: err.message,
          variant: "error",
        });
      } else {
        showToast({
          title: "Unexpected Error",
          description: "An unknown error occurred.",
          variant: "error",
        });
      }
    },
    [showToast]
  );

  return (
    <ToastContext.Provider value={{ toasts, showToast, showApiErrorToast, dismissToast }}>
      {children}
      <div
        aria-live="polite"
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-md w-full pointer-events-none px-4"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto rounded-lg border p-4 shadow-lg transition-all ${
              t.variant === "error"
                ? "bg-red-950/95 border-red-700 text-red-100"
                : t.variant === "success"
                  ? "bg-emerald-950/95 border-emerald-700 text-emerald-100"
                  : "bg-slate-900/95 border-slate-700 text-slate-100"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">{t.title}</p>
                <p className="text-xs mt-1 opacity-90">{t.description}</p>
                {t.requestId && (
                  <p className="text-[11px] font-mono mt-1.5 opacity-75">
                    request_id: {t.requestId}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismissToast(t.id)}
                className="text-xs opacity-70 hover:opacity-100 px-1.5 py-0.5 rounded border border-current"
                aria-label="Close notification"
              >
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}

