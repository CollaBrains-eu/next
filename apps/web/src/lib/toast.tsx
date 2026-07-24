import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

interface ToastItem {
  id: number;
  text: string;
  onUndo?: () => void;
}

interface ToastContextValue {
  showToast: (text: string, options?: { onUndo?: () => void }) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timeoutIdsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const timeoutIds = timeoutIdsRef.current;
    return () => {
      for (const timeoutId of timeoutIds) clearTimeout(timeoutId);
    };
  }, []);

  const showToast = useCallback((text: string, options?: { onUndo?: () => void }) => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, text, onUndo: options?.onUndo }]);
    const timeoutId = setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
    timeoutIdsRef.current.push(timeoutId);
  }, []);

  function handleUndo(toast: ToastItem) {
    toast.onUndo?.();
    setToasts((prev) => prev.filter((t) => t.id !== toast.id));
  }

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed right-4 top-4 z-[60] flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="min-w-[220px] rounded-xl border border-edge bg-surface px-4 py-3 text-sm shadow-overlay"
          >
            <span>{t.text}</span>
            {t.onUndo && (
              <button className="ml-2.5 font-bold text-accent" onClick={() => handleUndo(t)}>
                Undo
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}
