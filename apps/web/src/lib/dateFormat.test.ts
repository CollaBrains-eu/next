import { describe, expect, it } from "vitest";
import {
  DEFAULT_DATE_FORMAT_PREFS,
  formatDate,
  formatDateTime,
  formatTime,
  parseCompactDate,
  toDateFormatPrefs,
  type DateFormatPrefs,
} from "./dateFormat";

const EU: DateFormatPrefs = { dateFormat: "eu", timeFormat: "h24" };
const US: DateFormatPrefs = { dateFormat: "us", timeFormat: "h12" };
const ISO: DateFormatPrefs = { dateFormat: "iso", timeFormat: "h24" };

const SAMPLE = new Date(2026, 11, 31, 14, 30); // 31 Dec 2026, 14:30 local time

describe("formatDate", () => {
  it("formats eu as DD/MM/YYYY", () => {
    expect(formatDate(SAMPLE, EU)).toBe("31/12/2026");
  });

  it("formats us as MM/DD/YYYY", () => {
    expect(formatDate(SAMPLE, US)).toBe("12/31/2026");
  });

  it("formats iso as YYYY-MM-DD", () => {
    expect(formatDate(SAMPLE, ISO)).toBe("2026-12-31");
  });

  it("accepts an ISO string as well as a Date", () => {
    expect(formatDate("2026-12-31T00:00:00", EU)).toBe("31/12/2026");
  });

  it("returns the original string unchanged for unparsable input", () => {
    expect(formatDate("not-a-date", EU)).toBe("not-a-date");
  });
});

describe("formatTime", () => {
  it("formats h24 as HH:MM", () => {
    expect(formatTime(SAMPLE, EU)).toBe("14:30");
  });

  it("formats h12 with AM/PM", () => {
    expect(formatTime(SAMPLE, US)).toBe("2:30 PM");
  });

  it("formats midnight as 12 AM in h12", () => {
    expect(formatTime(new Date(2026, 0, 1, 0, 5), US)).toBe("12:05 AM");
  });

  it("formats noon as 12 PM in h12", () => {
    expect(formatTime(new Date(2026, 0, 1, 12, 0), US)).toBe("12:00 PM");
  });
});

describe("formatDateTime", () => {
  it("joins the date and time with a space", () => {
    expect(formatDateTime(SAMPLE, EU)).toBe("31/12/2026 14:30");
  });
});

describe("parseCompactDate", () => {
  it("parses a valid YYYYMMDD string", () => {
    const parsed = parseCompactDate("20270225");
    expect(parsed).not.toBeNull();
    expect(formatDate(parsed!, EU)).toBe("25/02/2027");
  });

  it("returns null for a malformed string", () => {
    expect(parseCompactDate("2027-02-25")).toBeNull();
  });

  it("returns null for an empty string", () => {
    expect(parseCompactDate("")).toBeNull();
  });

  it("returns null for an impossible date", () => {
    expect(parseCompactDate("20271345")).toBeNull();
  });
});

describe("toDateFormatPrefs", () => {
  it("returns the given valid values", () => {
    expect(toDateFormatPrefs("us", "h12")).toEqual({ dateFormat: "us", timeFormat: "h12" });
  });

  it("falls back to eu/h24 for null values", () => {
    expect(toDateFormatPrefs(null, null)).toEqual(DEFAULT_DATE_FORMAT_PREFS);
  });

  it("falls back to eu/h24 for unrecognized values", () => {
    expect(toDateFormatPrefs("klingon", "whenever")).toEqual(DEFAULT_DATE_FORMAT_PREFS);
  });
});
