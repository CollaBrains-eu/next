import { describe, expect, it } from "vitest";
import { fromDatetimeLocalValue, getMonthGridDates, toDateKey, toDatetimeLocalValue } from "./calendarGrid";

describe("toDateKey", () => {
  it("formats a date as YYYY-MM-DD in local time", () => {
    expect(toDateKey(new Date(2026, 6, 4))).toBe("2026-07-04");
  });
});

describe("getMonthGridDates", () => {
  it("returns 42 dates starting on the Monday on/before the 1st", () => {
    const dates = getMonthGridDates(2026, 6); // July 2026: the 1st is a Wednesday
    expect(dates).toHaveLength(42);
    expect(toDateKey(dates[0])).toBe("2026-06-29");
    expect(toDateKey(dates[41])).toBe("2026-08-09");
  });

  it("includes the 1st and last day of the target month", () => {
    const keys = getMonthGridDates(2026, 6).map(toDateKey);
    expect(keys).toContain("2026-07-01");
    expect(keys).toContain("2026-07-31");
  });
});

describe("toDatetimeLocalValue / fromDatetimeLocalValue", () => {
  it("round-trips a local date/time through the datetime-local string format", () => {
    const original = new Date(2026, 6, 14, 9, 30);
    const asLocalString = toDatetimeLocalValue(original.toISOString());
    expect(asLocalString).toBe("2026-07-14T09:30");
    const backToIso = fromDatetimeLocalValue(asLocalString);
    expect(new Date(backToIso).getTime()).toBe(original.getTime());
  });
});
