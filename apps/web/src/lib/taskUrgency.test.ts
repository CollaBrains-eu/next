import { describe, expect, it, vi } from "vitest";
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
