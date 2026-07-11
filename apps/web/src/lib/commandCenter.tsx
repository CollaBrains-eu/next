// apps/web/src/lib/commandCenter.tsx
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export type CommandCenterOverlay = "none" | "palette" | "shortcuts";

interface CommandCenterContextValue {
  overlay: CommandCenterOverlay;
  setOverlay: (overlay: CommandCenterOverlay) => void;
  openPalette: () => void;
}

const CommandCenterContext = createContext<CommandCenterContextValue | null>(null);

export function CommandCenterStateProvider({ children }: { children: ReactNode }) {
  const [overlay, setOverlay] = useState<CommandCenterOverlay>("none");
  const openPalette = useCallback(() => setOverlay("palette"), []);

  return (
    <CommandCenterContext.Provider value={{ overlay, setOverlay, openPalette }}>
      {children}
    </CommandCenterContext.Provider>
  );
}

export function useCommandCenterState(): CommandCenterContextValue {
  const ctx = useContext(CommandCenterContext);
  if (!ctx) throw new Error("useCommandCenterState must be used within CommandCenterStateProvider");
  return ctx;
}
