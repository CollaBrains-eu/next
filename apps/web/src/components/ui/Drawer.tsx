import { useEffect, useState, type ReactNode } from "react";
import { useEscapeToClose } from "../../hooks/useEscapeToClose";
import { Tooltip } from "./Tooltip";

interface DrawerTab {
  id: string;
  label: string;
  content: ReactNode;
}

export function Drawer({
  open,
  onClose,
  title,
  tabs,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  tabs: DrawerTab[];
  footer?: ReactNode;
}) {
  const [activeTabId, setActiveTabId] = useState(tabs[0]?.id);

  useEffect(() => {
    if (open) setActiveTabId(tabs[0]?.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEscapeToClose(open, onClose);

  if (!open) return null;

  const activeTab = tabs.find((tab) => tab.id === activeTabId) ?? tabs[0];

  return (
    <>
      <div
        data-testid="drawer-backdrop"
        className="fixed inset-0 z-[80] bg-[#0D0C1A]/35 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="fixed bottom-0 right-0 top-0 z-[81] flex w-[min(380px,92vw)] flex-col border-l border-edge bg-surface shadow-overlay">
        <div className="flex items-start justify-between border-b border-edge p-5">
          <h4 className="text-base font-semibold text-ink">{title}</h4>
          <Tooltip label="Close">
            <button aria-label="Close" onClick={onClose} className="rounded-lg p-1 text-ink-2 hover:bg-hover hover:text-ink">
              ✕
            </button>
          </Tooltip>
        </div>
        <div className="flex gap-4 border-b border-edge px-5">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTabId(tab.id)}
              className={`border-b-2 py-2.5 text-xs transition-colors duration-fast ${
                tab.id === activeTab.id ? "border-accent font-semibold text-accent" : "border-transparent text-ink-2"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-5">{activeTab.content}</div>
        {footer && <div className="flex gap-2 border-t border-edge p-4">{footer}</div>}
      </div>
    </>
  );
}
