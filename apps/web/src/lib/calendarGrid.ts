function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function toDateKey(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export function getMonthGridDates(year: number, month: number): Date[] {
  const firstOfMonth = new Date(year, month, 1);
  // JS getDay() is 0=Sun..6=Sat; shift so the grid starts on Monday.
  const firstWeekday = (firstOfMonth.getDay() + 6) % 7;
  const gridStart = new Date(year, month, 1 - firstWeekday);

  const dates: Date[] = [];
  for (let i = 0; i < 42; i++) {
    dates.push(new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i));
  }
  return dates;
}

export function toDatetimeLocalValue(isoUtc: string): string {
  const d = new Date(isoUtc);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

export function fromDatetimeLocalValue(value: string): string {
  return new Date(value).toISOString();
}
