import { useEffect } from "react";

export function useEscapeToClose(active: boolean, onClose: () => void): void {
  useEffect(() => {
    if (!active) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [active, onClose]);
}
