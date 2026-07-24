// apps/web/src/components/CommandCenter.tsx
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { NAV_ITEMS } from "../lib/navigation";
import { CommandPalette, type CommandItem } from "./ui/CommandPalette";
import { ShortcutsSheet } from "./ui/ShortcutsSheet";
import { useDarkMode } from "../hooks/useDarkMode";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { useCommandCenterState } from "../lib/commandCenter";
import { search } from "../lib/api";

export function CommandCenter() {
  const { overlay, setOverlay } = useCommandCenterState();
  const navigate = useNavigate();
  const { toggle: toggleDarkMode } = useDarkMode();
  const { t } = useTranslation();

  const [query, setQuery] = useState("");
  const [docItems, setDocItems] = useState<CommandItem[]>([]);
  const [searching, setSearching] = useState(false);
  const debouncedQuery = useDebouncedValue(query, 300);
  const latestRequestId = useRef(0);

  useEffect(() => {
    if (overlay !== "palette") {
      setQuery("");
      setDocItems([]);
    }
  }, [overlay]);

  useEffect(() => {
    if (debouncedQuery.trim().length < 2) {
      setDocItems([]);
      return;
    }
    const requestId = ++latestRequestId.current;
    setSearching(true);
    search(debouncedQuery.trim(), 5)
      .then((results) => {
        if (requestId !== latestRequestId.current) return;
        setDocItems(
          results.map((r) => ({
            label: r.document_title,
            description: r.content.slice(0, 120),
            group: "documents" as const,
            onSelect: () => navigate(`/documents/${r.document_id}`),
          }))
        );
      })
      .finally(() => {
        if (requestId === latestRequestId.current) setSearching(false);
      });
  }, [debouncedQuery, navigate]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTyping = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA";

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOverlay(overlay === "palette" ? "none" : "palette");
      } else if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "d") {
        event.preventDefault();
        toggleDarkMode();
      } else if (event.key === "?" && !isTyping) {
        event.preventDefault();
        setOverlay(overlay === "shortcuts" ? "none" : "shortcuts");
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [toggleDarkMode, overlay, setOverlay]);

  const items = NAV_ITEMS.map((item) => ({
    label: `Go to ${t(item.labelKey)}`,
    onSelect: () => navigate(item.to),
  }));

  return (
    <>
      <CommandPalette
        open={overlay === "palette"}
        onClose={() => setOverlay("none")}
        items={items}
        asyncItems={docItems}
        asyncLoading={searching}
        onQueryChange={setQuery}
      />
      <ShortcutsSheet open={overlay === "shortcuts"} onClose={() => setOverlay("none")} />
    </>
  );
}
