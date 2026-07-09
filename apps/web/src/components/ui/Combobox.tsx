import { useMemo, useRef, useState } from "react";
import { useClickOutside } from "../../hooks/useClickOutside";

export interface ComboboxOption {
  id: string;
  label: string;
}

export function Combobox({
  options,
  selected,
  onChange,
  placeholder = "Search…",
}: {
  options: ComboboxOption[];
  selected: ComboboxOption[];
  onChange: (next: ComboboxOption[]) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  useClickOutside(rootRef, open, () => setOpen(false));

  const selectedIds = useMemo(() => new Set(selected.map((s) => s.id)), [selected]);
  const filtered = useMemo(
    () => options.filter((o) => o.label.toLowerCase().includes(query.toLowerCase())),
    [options, query],
  );

  function remove(id: string) {
    onChange(selected.filter((s) => s.id !== id));
  }

  function add(option: ComboboxOption) {
    if (!selectedIds.has(option.id)) onChange([...selected, option]);
    setQuery("");
  }

  return (
    <div ref={rootRef} className="relative max-w-[340px]">
      <div
        className="flex min-h-[38px] flex-wrap items-center gap-1.5 rounded-xl border border-edge bg-surface p-1.5 transition-colors duration-fast focus-within:border-accent focus-within:shadow-[0_0_0_3px_var(--accent-bg)]"
        onClick={() => setOpen(true)}
      >
        {selected.map((s) => (
          <span
            key={s.id}
            className="inline-flex items-center gap-1 rounded-full bg-accent-soft py-0.5 pl-2.5 pr-1 text-xs font-semibold text-accent"
          >
            {s.label}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                remove(s.id);
              }}
              className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-accent/20 text-[9px] leading-none"
              aria-label={`Remove ${s.label}`}
            >
              &times;
            </button>
          </span>
        ))}
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setOpen(true)}
          placeholder={selected.length === 0 ? placeholder : ""}
          className="min-w-[80px] flex-1 border-none bg-transparent p-1 text-[13px] text-ink outline-none"
        />
      </div>
      <div
        role="listbox"
        className={`absolute left-0 right-0 top-[calc(100%+6px)] z-20 max-h-[180px] overflow-y-auto rounded-xl border border-edge bg-surface p-1.5 shadow-overlay transition-all duration-base ease-spring ${
          open ? "pointer-events-auto translate-y-0 scale-100 opacity-100" : "pointer-events-none -translate-y-1.5 scale-[.97] opacity-0"
        }`}
      >
        {filtered.length === 0 ? (
          <div className="px-2.5 py-2 text-[13px] text-ink-3">No matches</div>
        ) : (
          filtered.map((option) => {
            const isSelected = selectedIds.has(option.id);
            return (
              <button
                key={option.id}
                type="button"
                disabled={isSelected}
                onClick={() => add(option)}
                className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors duration-fast ${
                  isSelected ? "cursor-default text-ink-3 opacity-40" : "text-ink-2 hover:bg-hover hover:text-ink"
                }`}
              >
                {option.label}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
