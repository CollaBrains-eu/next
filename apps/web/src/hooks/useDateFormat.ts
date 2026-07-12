import { useMemo, useSyncExternalStore } from "react";
import {
  DEFAULT_DATE_FORMAT_PREFS,
  formatDate,
  formatDateTime,
  formatTime,
  type DateFormatPrefs,
} from "../lib/dateFormat";

let currentPrefs: DateFormatPrefs = DEFAULT_DATE_FORMAT_PREFS;
const listeners = new Set<() => void>();

// Plain-function singleton, same shape as auth.tsx's syncLanguage(): callers
// (AuthProvider on preferences load, Settings on save) call this directly;
// useDateFormat() below subscribes React components to it reactively.
export function setDateFormatPrefs(prefs: DateFormatPrefs): void {
  currentPrefs = prefs;
  listeners.forEach((listener) => listener());
}

function getSnapshot(): DateFormatPrefs {
  return currentPrefs;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useDateFormat() {
  const prefs = useSyncExternalStore(subscribe, getSnapshot);
  return useMemo(
    () => ({
      formatDate: (value: string | Date) => formatDate(value, prefs),
      formatTime: (value: string | Date) => formatTime(value, prefs),
      formatDateTime: (value: string | Date) => formatDateTime(value, prefs),
    }),
    [prefs],
  );
}
