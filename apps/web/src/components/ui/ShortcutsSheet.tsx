import { useEscapeToClose } from "../../hooks/useEscapeToClose";

const SHORTCUTS: { label: string; keys: string }[] = [
  { label: "Open command palette", keys: "⌘K" },
  { label: "Show this sheet", keys: "?" },
  { label: "Close any overlay", keys: "Esc" },
  { label: "Toggle dark mode", keys: "⌘D" },
];

export function ShortcutsSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEscapeToClose(open, onClose);

  if (!open) return null;

  return (
    <>
      <div data-testid="shortcuts-backdrop" className="fixed inset-0 z-50 bg-[#0D0C1A]/35 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed left-1/2 top-[15%] z-[51] w-[min(420px,90vw)] -translate-x-1/2 overflow-hidden rounded-2xl border border-edge bg-surface shadow-overlay">
        <div className="border-b border-edge px-5 py-4 text-sm font-semibold text-ink">Keyboard shortcuts</div>
        {SHORTCUTS.map((shortcut) => (
          <div key={shortcut.label} className="flex items-center justify-between px-5 py-2.5 text-sm text-ink-2">
            <span>{shortcut.label}</span>
            <kbd className="rounded-md bg-accent-soft px-1.5 py-0.5 text-xs text-accent">{shortcut.keys}</kbd>
          </div>
        ))}
      </div>
    </>
  );
}
