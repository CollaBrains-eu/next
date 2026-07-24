import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

interface LoadingBarContextValue {
  start: () => void;
  done: () => void;
}

const LoadingBarContext = createContext<LoadingBarContextValue | null>(null);

export function LoadingBarProvider({ children }: { children: ReactNode }) {
  const [width, setWidth] = useState(0);
  const resetTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (resetTimeoutRef.current) clearTimeout(resetTimeoutRef.current);
    };
  }, []);

  const start = useCallback(() => {
    setWidth(70);
  }, []);

  const done = useCallback(() => {
    setWidth(100);
    resetTimeoutRef.current = setTimeout(() => setWidth(0), 300);
  }, []);

  return (
    <LoadingBarContext.Provider value={{ start, done }}>
      {children}
      <div
        data-testid="loading-bar"
        className="fixed left-0 top-0 z-[200] h-[3px] bg-accent transition-[width] duration-base ease-out-token"
        style={{ width: `${width}%` }}
      />
    </LoadingBarContext.Provider>
  );
}

export function useLoadingBar(): LoadingBarContextValue {
  const ctx = useContext(LoadingBarContext);
  if (!ctx) throw new Error("useLoadingBar must be used within a LoadingBarProvider");
  return ctx;
}
