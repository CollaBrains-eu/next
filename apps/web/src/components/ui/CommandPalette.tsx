import { useEffect, useState } from "react";
import { useEscapeToClose } from "../../hooks/useEscapeToClose";

interface CommandItem {
  label: string;
  onSelect: () => void;
}

export function CommandPalette({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: CommandItem[];
}) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  useEscapeToClose(open, onClose);

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
    }
  }, [open]);

  if (!open) return null;

  const filtered = items.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()));

  function runSelection(item: CommandItem) {
    item.onSelect();
    onClose();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const item = filtered[selectedIndex];
      if (item) runSelection(item);
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-50 bg-[#0D0C1A]/35 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed left-1/2 top-[18%] z-[51] w-[min(520px,90vw)] -translate-x-1/2 overflow-hidden rounded-2xl border border-edge bg-surface shadow-overlay">
        <input
          autoFocus
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setSelectedIndex(0);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search documents, cases, vehicles…"
          className="w-full border-b border-edge bg-transparent px-4 py-4 text-sm text-ink outline-none"
        />
        <div>
          {filtered.map((item, index) => (
            <div
              key={item.label}
              onClick={() => runSelection(item)}
              onMouseEnter={() => setSelectedIndex(index)}
              className={`cursor-pointer px-4 py-2.5 text-sm transition-colors duration-fast ${
                index === selectedIndex ? "bg-hover text-ink" : "text-ink-2"
              }`}
            >
              {item.label}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
