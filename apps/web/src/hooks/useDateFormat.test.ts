import { afterEach, describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { setDateFormatPrefs, useDateFormat } from "./useDateFormat";
import { DEFAULT_DATE_FORMAT_PREFS } from "../lib/dateFormat";

describe("useDateFormat", () => {
  afterEach(() => {
    act(() => setDateFormatPrefs(DEFAULT_DATE_FORMAT_PREFS));
  });

  it("formats using the default eu/h24 prefs initially", () => {
    const { result } = renderHook(() => useDateFormat());
    expect(result.current.formatDate(new Date(2026, 5, 1))).toBe("01/06/2026");
  });

  it("reactively updates already-mounted consumers when prefs change", () => {
    const { result } = renderHook(() => useDateFormat());
    act(() => setDateFormatPrefs({ dateFormat: "us", timeFormat: "h12" }));
    expect(result.current.formatDate(new Date(2026, 5, 1))).toBe("06/01/2026");
  });

  it("exposes formatTime and formatDateTime bound to the current prefs", () => {
    const { result } = renderHook(() => useDateFormat());
    act(() => setDateFormatPrefs({ dateFormat: "iso", timeFormat: "h24" }));
    const sample = new Date(2026, 5, 1, 9, 5);
    expect(result.current.formatTime(sample)).toBe("09:05");
    expect(result.current.formatDateTime(sample)).toBe("2026-06-01 09:05");
  });
});
