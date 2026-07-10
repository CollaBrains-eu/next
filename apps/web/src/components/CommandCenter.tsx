// apps/web/src/components/CommandCenter.tsx
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { NAV_ITEMS } from "../lib/navigation";
import { CommandPalette } from "./ui/CommandPalette";
import { ShortcutsSheet } from "./ui/ShortcutsSheet";
import { useDarkMode } from "../hooks/useDarkMode";
import { useCommandCenterState } from "../lib/commandCenter";

export function CommandCenter() {
  const { overlay, setOverlay } = useCommandCenterState();
  const navigate = useNavigate();
  const { toggle: toggleDarkMode } = useDarkMode();
  const { t } = useTranslation();

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
      <CommandPalette open={overlay === "palette"} onClose={() => setOverlay("none")} items={items} />
      <ShortcutsSheet open={overlay === "shortcuts"} onClose={() => setOverlay("none")} />
    </>
  );
}
