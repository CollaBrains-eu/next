import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useEscapeToClose } from "../../hooks/useEscapeToClose";

export interface CommandItem {
  label: string;
  onSelect: () => void;
  group?: "navigation" | "documents";
  description?: string;
}

export function CommandPalette({
  open,
  onClose,
  items,
  asyncItems,
  asyncLoading,
  onQueryChange,
}: {
  open: boolean;
  onClose: () => void;
  items: CommandItem[];
  asyncItems?: CommandItem[];
  asyncLoading?: boolean;
  onQueryChange?: (query: string) => void;
}) {
  const { t } = useTranslation();
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

  const filteredNav = items.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()));
  const docs = asyncItems ?? [];
  const filtered = [...filteredNav, ...docs];
  const showSearching = asyncLoading && query.trim().length >= 2;

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
            onQueryChange?.(event.target.value);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search documents, cases, vehicles…"
          className="w-full border-b border-edge bg-transparent px-4 py-4 text-sm text-ink outline-none"
        />
        <div className="max-h-[60vh] overflow-y-auto">
          {filteredNav.length > 0 && docs.length > 0 && (
            <div className="px-4 pt-3 text-[11px] font-semibold uppercase tracking-wide text-ink-3">
              {t("commandCenter.groupNavigation")}
            </div>
          )}
          {filteredNav.map((item, index) => (
            <div
              key={`nav-${index}-${item.label}`}
              onClick={() => runSelection(item)}
              onMouseEnter={() => setSelectedIndex(index)}
              className={`cursor-pointer px-4 py-2.5 text-sm transition-colors duration-fast ${
                index === selectedIndex ? "bg-hover text-ink" : "text-ink-2"
              }`}
            >
              {item.label}
            </div>
          ))}
          {docs.length > 0 && (
            <div className="px-4 pt-3 text-[11px] font-semibold uppercase tracking-wide text-ink-3">
              {t("commandCenter.groupDocuments")}
            </div>
          )}
          {showSearching && (
            <div className="px-4 py-2.5 text-sm text-ink-3">{t("commandCenter.searching")}</div>
          )}
          {docs.map((item, docIndex) => {
            const index = filteredNav.length + docIndex;
            return (
              <div
                key={`doc-${docIndex}-${item.label}`}
                onClick={() => runSelection(item)}
                onMouseEnter={() => setSelectedIndex(index)}
                className={`cursor-pointer px-4 py-2.5 text-sm transition-colors duration-fast ${
                  index === selectedIndex ? "bg-hover text-ink" : "text-ink-2"
                }`}
              >
                <div>{item.label}</div>
                {item.description && <div className="mt-0.5 truncate text-xs text-ink-3">{item.description}</div>}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
