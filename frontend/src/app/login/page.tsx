"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, setStoredTokens, clearStoredTokens } from "@/lib/api-client";
import { useToast } from "@/components/toast-provider";

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: {
    id: number;
    email: string;
    full_name: string;
    role: string;
  };
}

export default function LoginPage() {
  const [email, setEmail] = useState("admin@leadpulse.io");
  const [password, setPassword] = useState("Admin@123");
  const [loading, setLoading] = useState(false);
  const { showToast, showApiErrorToast } = useToast();
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await apiFetch<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setStoredTokens(
        data.access_token,
        data.refresh_token,
        data.user.role,
        data.user.email
      );
      showToast({
        title: `Signed in as ${data.user.full_name}`,
        description: `Role: ${data.user.role.toUpperCase()} — JWT access & refresh tokens stored.`,
        variant: "success",
      });
      router.push("/dashboard");
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setLoading(false);
    }
  }

  function fillDemo(role: "admin" | "agent") {
    if (role === "admin") {
      setEmail("admin@leadpulse.io");
      setPassword("Admin@123");
    } else {
      setEmail("agent@leadpulse.io");
      setPassword("Agent@123");
    }
  }

  return (
    <div className="mx-auto my-10 max-w-md rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
      <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
        JWT Auth + RBAC (Admin & Agent)
      </span>
      <h1 className="mt-1 text-xl font-bold text-white">Sign in to LeadPulse</h1>
      <p className="mt-1 text-xs text-slate-400">
        Passwords hashed with bcrypt. Issues 30-min access JWT + 7-day refresh JWT. Login rate-limited in Redis (10 req/min).
      </p>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => fillDemo("admin")}
          className="rounded-lg border border-blue-500/40 bg-blue-950/40 px-3 py-2 text-left text-xs hover:bg-blue-900/40"
        >
          <p className="font-semibold text-blue-300">Demo Admin</p>
          <p className="font-mono text-[11px] text-slate-300">admin@leadpulse.io</p>
          <p className="font-mono text-[10px] text-slate-400">Pass: Admin@123</p>
        </button>
        <button
          type="button"
          onClick={() => fillDemo("agent")}
          className="rounded-lg border border-emerald-500/40 bg-emerald-950/40 px-3 py-2 text-left text-xs hover:bg-emerald-900/40"
        >
          <p className="font-semibold text-emerald-300">Demo Sales Agent</p>
          <p className="font-mono text-[11px] text-slate-300">agent@leadpulse.io</p>
          <p className="font-mono text-[10px] text-slate-400">Pass: Agent@123</p>
        </button>
      </div>

      <form onSubmit={handleSubmit} className="mt-5 space-y-4">
        <div>
          <label
            htmlFor="login-email"
            className="block text-xs font-medium text-slate-300"
          >
            Email Address
          </label>
          <input
            id="login-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
          />
        </div>

        <div>
          <label
            htmlFor="login-password"
            className="block text-xs font-medium text-slate-300"
          >
            Password
          </label>
          <input
            id="login-password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign In & Issue JWT"}
          </button>
          <button
            type="button"
            onClick={() => {
              clearStoredTokens();
              showToast({
                title: "Signed Out",
                description: "Cleared stored JWT tokens.",
                variant: "info",
              });
            }}
            className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700"
          >
            Clear Token
          </button>
        </div>
      </form>
    </div>
  );
}

