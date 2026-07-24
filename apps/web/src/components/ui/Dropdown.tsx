import { useRef, useState, type ReactNode } from "react";
import { useClickOutside } from "../../hooks/useClickOutside";
import { useEscapeToClose } from "../../hooks/useEscapeToClose";

export interface DropdownOption {
  label: string;
  onSelect: () => void;
  danger?: boolean;
}

export function Dropdown({
  trigger,
  options,
  align = "left",
}: {
  trigger: ReactNode;
  options: DropdownOption[];
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useClickOutside(rootRef, open, () => setOpen(false));
  useEscapeToClose(open, () => setOpen(false));

  return (
    <div ref={rootRef} className="relative inline-block">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        {trigger}
      </button>
      <div
        role="menu"
        className={`absolute ${align === "right" ? "right-0" : "left-0"} top-[calc(100%+6px)] z-20 min-w-[170px] rounded-xl border border-edge bg-surface p-1.5 shadow-overlay transition-all duration-base ease-spring ${
          open ? "pointer-events-auto translate-y-0 scale-100 opacity-100" : "pointer-events-none -translate-y-1.5 scale-[.97] opacity-0"
        }`}
      >
        {options.map((option) => (
          <button
            key={option.label}
            role="menuitem"
            type="button"
            onClick={() => {
              option.onSelect();
              setOpen(false);
            }}
            className={`block w-full rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors duration-fast ${
              option.danger ? "text-danger hover:bg-danger-soft" : "text-ink-2 hover:bg-hover hover:text-ink"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
