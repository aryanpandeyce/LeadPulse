import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "@/hooks/use-debounce";

describe("useDebounce Hook (Concept 2: 300ms Debounced Search)", () => {
  it("debounces rapid search input updates by 300ms", async () => {
    const { result, rerender } = renderHook(
      ({ val }) => useDebounce(val, 50),
      { initialProps: { val: "a" } }
    );

    expect(result.current).toBe("a");
    rerender({ val: "aryan" });
    // Before 50ms elapses, value is still "a"
    expect(result.current).toBe("a");

    await act(async () => {
      await new Promise((r) => setTimeout(r, 70));
    });
    expect(result.current).toBe("aryan");
  });
});

