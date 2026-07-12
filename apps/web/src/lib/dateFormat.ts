export type DateFormat = "eu" | "us" | "iso";
export type TimeFormat = "h24" | "h12";

export interface DateFormatPrefs {
  dateFormat: DateFormat;
  timeFormat: TimeFormat;
}

export const DEFAULT_DATE_FORMAT_PREFS: DateFormatPrefs = { dateFormat: "eu", timeFormat: "h24" };

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function toDate(value: string | Date): Date | null {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value: string | Date, prefs: DateFormatPrefs): string {
  const date = toDate(value);
  if (!date) return String(value);
  const day = pad2(date.getDate());
  const month = pad2(date.getMonth() + 1);
  const year = date.getFullYear();
  switch (prefs.dateFormat) {
    case "us":
      return `${month}/${day}/${year}`;
    case "iso":
      return `${year}-${month}-${day}`;
    case "eu":
    default:
      return `${day}/${month}/${year}`;
  }
}

export function formatTime(value: string | Date, prefs: DateFormatPrefs): string {
  const date = toDate(value);
  if (!date) return String(value);
  const hours24 = date.getHours();
  const minutes = pad2(date.getMinutes());
  if (prefs.timeFormat === "h12") {
    const period = hours24 < 12 ? "AM" : "PM";
    const hours12 = hours24 % 12 === 0 ? 12 : hours24 % 12;
    return `${hours12}:${minutes} ${period}`;
  }
  return `${pad2(hours24)}:${minutes}`;
}

export function formatDateTime(value: string | Date, prefs: DateFormatPrefs): string {
  const date = toDate(value);
  if (!date) return String(value);
  return `${formatDate(date, prefs)} ${formatTime(date, prefs)}`;
}

// RDW returns APK expiry as a compact "YYYYMMDD" string, not ISO.
export function parseCompactDate(value: string): Date | null {
  const match = /^(\d{4})(\d{2})(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
  return date;
}

export function toDateFormatPrefs(dateFormat: string | null, timeFormat: string | null): DateFormatPrefs {
  const df: DateFormat = dateFormat === "us" || dateFormat === "iso" ? dateFormat : "eu";
  const tf: TimeFormat = timeFormat === "h12" ? "h12" : "h24";
  return { dateFormat: df, timeFormat: tf };
}
