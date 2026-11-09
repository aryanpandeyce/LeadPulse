import { describe, expect, it, vi } from "vitest";
import { ApiClientError, apiFetch } from "@/lib/api-client";

describe("Typed API Client & Unified Error Envelope (Concept 4)", () => {
  it("parses canonical backend error envelope into ApiClientError with requestId and Retry-After", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      statusText: "Too Many Requests",
      headers: new Headers({
        "X-Request-ID": "req-abc-123",
        "Retry-After": "45",
      }),
      json: async () => ({
        error: {
          code: "AI_RATE_LIMIT_EXCEEDED",
          message: "Rate limit of 20 AI requests per minute exceeded.",
          status: 429,
          request_id: "req-abc-123",
          details: [{ field: "user_id", issue: "21/20 requests in window" }],
        },
      }),
    });

    vi.stubGlobal("fetch", mockFetch);

    await expect(apiFetch("/ai/chat")).rejects.toThrowError(ApiClientError);

    try {
      await apiFetch("/ai/chat");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiClientError);
      const apiErr = err as ApiClientError;
      expect(apiErr.code).toBe("AI_RATE_LIMIT_EXCEEDED");
      expect(apiErr.status).toBe(429);
      expect(apiErr.requestId).toBe("req-abc-123");
      expect(apiErr.retryAfterSeconds).toBe(45);
      expect(apiErr.details).toHaveLength(1);
    }
  });
});

