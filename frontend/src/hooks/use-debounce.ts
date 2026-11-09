"use client";

import { useEffect, useState } from "react";

/**
 * Custom hook that debounces a changing value by `delayMs` (default 300ms).
 * Used on `/customers` search input so typing "aryan" doesn't fire 5 API calls.
 */
export function useDebounce<T>(value: T, delayMs = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delayMs]);

  return debouncedValue;
}
