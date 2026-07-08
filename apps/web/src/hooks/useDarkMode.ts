import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "cb-theme";

function applyClass(isDark: boolean) {
  document.documentElement.classList.toggle("dark", isDark);
}

export function useDarkMode(): { isDark: boolean; toggle: () => void } {
  const [isDark, setIsDark] = useState(() => localStorage.getItem(STORAGE_KEY) === "dark");

  useEffect(() => {
    applyClass(isDark);
  }, [isDark]);

  const toggle = useCallback(() => {
    setIsDark((prev) => {
      const next = !prev;
      localStorage.setItem(STORAGE_KEY, next ? "dark" : "light");
      return next;
    });
  }, []);

  return { isDark, toggle };
}
