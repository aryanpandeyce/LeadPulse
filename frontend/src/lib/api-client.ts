/**
 * Typed API Client that parses the unified backend Error Envelope (Concept 4)
 * and attaches JWT Bearer tokens + X-Request-ID correlation headers.
 *
 * # CONCEPT: Error handling & good error design (Typed Frontend API Client)
 */

export interface ErrorDetail {
  field: string;
  issue: string;
  type?: string;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    status: number;
    request_id: string;
    details: ErrorDetail[];
  };
}

export class ApiClientError extends Error {
  public readonly code: string;
  public readonly status: number;
  public readonly requestId: string;
  public readonly details: ErrorDetail[];
  public readonly retryAfterSeconds?: number;

  constructor(envelope: ApiErrorEnvelope["error"], retryAfter?: string | null) {
    super(envelope.message);
    this.name = "ApiClientError";
    this.code = envelope.code;
    this.status = envelope.status;
    this.requestId = envelope.request_id;
    this.details = envelope.details || [];
    if (retryAfter) {
      const parsed = Number.parseInt(retryAfter, 10);
      if (!Number.isNaN(parsed)) {
        this.retryAfterSeconds = parsed;
      }
    }
  }
}

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type ColdStartListener = (wakingUp: boolean) => void;
const coldStartListeners = new Set<ColdStartListener>();

export function subscribeColdStart(listener: ColdStartListener): () => void {
  coldStartListeners.add(listener);
  return () => {
    coldStartListeners.delete(listener);
  };
}

function notifyColdStart(wakingUp: boolean): void {
  coldStartListeners.forEach((fn) => fn(wakingUp));
}

export function getStoredAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("leadpulse_access_token");
}

export function setStoredTokens(accessToken: string, refreshToken: string, userRole: string, userEmail: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem("leadpulse_access_token", accessToken);
  window.localStorage.setItem("leadpulse_refresh_token", refreshToken);
  window.localStorage.setItem("leadpulse_user_role", userRole);
  window.localStorage.setItem("leadpulse_user_email", userEmail);
}

export function clearStoredTokens(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("leadpulse_access_token");
  window.localStorage.removeItem("leadpulse_refresh_token");
  window.localStorage.removeItem("leadpulse_user_role");
  window.localStorage.removeItem("leadpulse_user_email");
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<{ data: T; requestId: string; responseTimeMs: string }> {
  const token = getStoredAccessToken();
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE_URL}${endpoint}`;
  let coldTimer: ReturnType<typeof setTimeout> | null = setTimeout(() => {
    notifyColdStart(true);
  }, 3500);

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } finally {
    if (coldTimer) {
      clearTimeout(coldTimer);
      coldTimer = null;
    }
    notifyColdStart(false);
  }

  const requestId = response.headers.get("X-Request-ID") || "unknown";
  const responseTimeMs = response.headers.get("X-Response-Time-Ms") || "0";

  if (!response.ok) {
    let parsedEnvelope: ApiErrorEnvelope | null = null;
    try {
      parsedEnvelope = (await response.json()) as ApiErrorEnvelope;
    } catch {
      // Fallback if response wasn't JSON
    }

    if (parsedEnvelope && parsedEnvelope.error) {
      throw new ApiClientError(
        parsedEnvelope.error,
        response.headers.get("Retry-After")
      );
    }

    throw new ApiClientError({
      code: `HTTP_${response.status}`,
      message: response.statusText || "Request failed",
      status: response.status,
      request_id: requestId,
      details: [],
    });
  }

  const data = (await response.json()) as T;
  return { data, requestId, responseTimeMs };
}

