import type { ReactNode } from "react";
import { useEscapeToClose } from "../../hooks/useEscapeToClose";

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  useEscapeToClose(open, onClose);

  if (!open) return null;

  return (
    <>
      <div
        data-testid="modal-backdrop"
        className="fixed inset-0 z-[70] bg-[#0D0C1A]/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="fixed left-1/2 top-1/2 z-[71] max-h-[85vh] w-[min(380px,90vw)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-edge bg-surface p-6 shadow-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <h4 className="mb-2 text-base font-semibold text-ink">{title}</h4>
        {children}
      </div>
    </>
  );
}
