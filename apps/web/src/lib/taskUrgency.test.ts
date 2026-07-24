import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { taskUrgency, daysUntil, relativeDueLabel } from "./taskUrgency";

function isoDate(offsetDays: number): string {
  return new Date(Date.now() + offsetDays * 86400000).toISOString().slice(0, 10);
}

describe("taskUrgency", () => {
  it("returns danger with overdueDays for a past due date", () => {
    expect(taskUrgency(isoDate(-3))).toEqual({ variant: "danger", overdueDays: 3 });
  });

  it("returns warning with null overdueDays for today's due date", () => {
    expect(taskUrgency(isoDate(0))).toEqual({ variant: "warning", overdueDays: null });
  });

  it("returns default with null overdueDays for a future due date", () => {
    expect(taskUrgency(isoDate(5))).toEqual({ variant: "default", overdueDays: null });
  });
});

describe("daysUntil", () => {
  it("returns a positive count for a future date", () => {
    expect(daysUntil(isoDate(4))).toBe(4);
  });

  it("returns 0 for today", () => {
    expect(daysUntil(isoDate(0))).toBe(0);
  });

  it("returns a negative count for a past date", () => {
    expect(daysUntil(isoDate(-2))).toBe(-2);
  });
});

describe("relativeDueLabel", () => {
  const t = vi.fn((key: string, opts?: Record<string, unknown>) => {
    if (key === "tasks.dueOverdue") return `Overdue by ${opts?.count} days`;
    if (key === "tasks.dueToday") return "Due today";
    if (key === "tasks.dueTomorrow") return "Due tomorrow";
    if (key === "tasks.dueInDays") return `Due in ${opts?.count} days`;
    if (key === "tasks.due") return `Due ${opts?.date}`;
    return key;
  });
  const formatDate = (value: string) => value;

  it("labels an overdue date", () => {
    expect(relativeDueLabel(isoDate(-2), t, formatDate)).toBe("Overdue by 2 days");
  });

  it("labels today", () => {
    expect(relativeDueLabel(isoDate(0), t, formatDate)).toBe("Due today");
  });

  it("labels tomorrow distinctly from other near-future days", () => {
    expect(relativeDueLabel(isoDate(1), t, formatDate)).toBe("Due tomorrow");
  });

  it("labels a date within a week as 'in N days'", () => {
    expect(relativeDueLabel(isoDate(5), t, formatDate)).toBe("Due in 5 days");
  });

  it("falls back to the formatted date beyond a week out", () => {
    expect(relativeDueLabel(isoDate(10), t, formatDate)).toBe(`Due ${isoDate(10)}`);
  });
});

describe("taskUrgency — null/invalid dates and overdue cap", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-24T00:00:00Z"));
  });
  afterEach(() => vi.useRealTimers());

  it("returns 'unknown' for a missing due date instead of crashing", () => {
    expect(taskUrgency(null).variant).toBe("unknown");
    expect(taskUrgency(undefined).variant).toBe("unknown");
    expect(taskUrgency("").variant).toBe("unknown");
  });

  it("returns 'unknown' for an unparseable due date instead of NaN", () => {
    expect(taskUrgency("not-a-date").variant).toBe("unknown");
  });

  it("computes overdueDays correctly for a genuinely old valid date", () => {
    const result = taskUrgency("2019-04-09");
    expect(result.variant).toBe("danger");
    expect(result.overdueDays).toBeGreaterThan(2000);
  });

  it("relativeDueLabel shows 'No date on file' for missing/invalid dates", () => {
    const t = (key: string) => ({ "tasks.dueUnknown": "No date on file" } as Record<string, string>)[key] ?? key;
    expect(relativeDueLabel(null, t, (d) => d)).toBe("No date on file");
    expect(relativeDueLabel("garbage", t, (d) => d)).toBe("No date on file");
  });

  it("relativeDueLabel shows the absolute date, not a raw day count, past 365 days overdue", () => {
    const t = (key: string, opts?: Record<string, unknown>) =>
      key === "tasks.dueOverdueSince" ? `Overdue since ${opts?.date}` : key;
    const formatDate = (_d: string) => "9 Apr 2019";
    expect(relativeDueLabel("2019-04-09", t, formatDate)).toBe("Overdue since 9 Apr 2019");
  });
});
