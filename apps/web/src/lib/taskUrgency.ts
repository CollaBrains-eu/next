export type UrgencyVariant = "danger" | "warning" | "default" | "unknown";

export interface TaskUrgency {
  variant: UrgencyVariant;
  overdueDays: number | null;
}

const OVERDUE_DAYS_ABSOLUTE_CUTOFF = 365;

function isValidDateString(value: string): boolean {
  return !Number.isNaN(new Date(value).getTime());
}

export function taskUrgency(dueDate: string | null | undefined): TaskUrgency {
  if (!dueDate || !isValidDateString(dueDate)) {
    return { variant: "unknown", overdueDays: null };
  }
  const today = new Date().toISOString().slice(0, 10);
  if (dueDate < today) {
    const days = Math.round((new Date(today).getTime() - new Date(dueDate).getTime()) / 86400000);
    return { variant: "danger", overdueDays: days };
  }
  if (dueDate === today) {
    return { variant: "warning", overdueDays: null };
  }
  return { variant: "default", overdueDays: null };
}

export function daysUntil(dueDate: string): number {
  const today = new Date().toISOString().slice(0, 10);
  return Math.round((new Date(dueDate).getTime() - new Date(today).getTime()) / 86400000);
}

export function relativeDueLabel(
  dueDate: string | null | undefined,
  t: (key: string, opts?: Record<string, unknown>) => string,
  formatDate: (value: string) => string,
): string {
  const urgency = taskUrgency(dueDate);
  if (urgency.variant === "unknown") return t("tasks.dueUnknown");
  if (urgency.variant === "danger") {
    if (urgency.overdueDays !== null && urgency.overdueDays > OVERDUE_DAYS_ABSOLUTE_CUTOFF) {
      return t("tasks.dueOverdueSince", { date: formatDate(dueDate as string) });
    }
    return t("tasks.dueOverdue", { count: urgency.overdueDays });
  }
  if (urgency.variant === "warning") return t("tasks.dueToday");
  const days = daysUntil(dueDate as string);
  if (days === 1) return t("tasks.dueTomorrow");
  if (days <= 7) return t("tasks.dueInDays", { count: days });
  return t("tasks.due", { date: formatDate(dueDate as string) });
}
