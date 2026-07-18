import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useDebouncedValue } from "./useDebouncedValue";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useDebouncedValue", () => {
  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("a", 300));
    expect(result.current).toBe("a");
  });

  it("does not update before the delay elapses", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: "a" },
    });
    rerender({ value: "ab" });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe("a");
  });

  it("updates once the delay elapses", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: "a" },
    });
    rerender({ value: "ab" });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe("ab");
  });

  it("resets the timer on rapid successive updates", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: "a" },
    });
    rerender({ value: "ab" });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    rerender({ value: "abc" });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe("a");
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(result.current).toBe("abc");
  });
});
