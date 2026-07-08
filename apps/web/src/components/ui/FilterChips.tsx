import { useState } from "react";

interface FilterOption {
  id: string;
  label: string;
}

export function FilterChips({
  chips,
  onRemove,
  addOptions,
  onAdd,
}: {
  chips: FilterOption[];
  onRemove: (id: string) => void;
  addOptions: FilterOption[];
  onAdd: (option: FilterOption) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((chip) => (
        <span
          key={chip.id}
          className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft py-1 pl-3 pr-1.5 text-xs font-semibold text-accent"
        >
          {chip.label}
          <button
            aria-label={`Remove ${chip.label}`}
            onClick={() => onRemove(chip.id)}
            className="flex h-4 w-4 items-center justify-center rounded-full bg-accent/20 text-[10px] hover:bg-accent/30"
          >
            ✕
          </button>
        </span>
      ))}
      <div className="relative">
        <button
          onClick={() => setMenuOpen((prev) => !prev)}
          className="rounded-full border border-dashed border-edge px-3 py-1 text-xs font-semibold text-ink-2 transition-colors duration-fast hover:border-accent hover:text-accent"
        >
          + Add filter
        </button>
        {menuOpen && (
          <div className="absolute left-0 top-full z-20 mt-1.5 min-w-[170px] rounded-xl border border-edge bg-surface p-1.5 shadow-overlay">
            {addOptions.map((option) => (
              <div
                key={option.id}
                onClick={() => {
                  onAdd(option);
                  setMenuOpen(false);
                }}
                className="cursor-pointer rounded-lg px-3 py-2 text-sm text-ink-2 hover:bg-hover hover:text-ink"
              >
                {option.label}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
