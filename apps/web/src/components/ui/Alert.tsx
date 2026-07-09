import { useState, type ReactNode } from "react";

type Variant = "info" | "success" | "warning" | "danger";

const VARIANT_CLASSES: Record<Variant, string> = {
  info: "bg-accent-soft text-accent",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
};

const ICONS: Record<Variant, ReactNode> = {
  info: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M8 7.2v3.6M8 5.2h.01" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
  success: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  warning: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8 1.5l7 12.5H1L8 1.5z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M8 6.5v3M8 11.5h.01" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
  danger: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
};

export function Alert({
  variant = "info",
  title,
  children,
  dismissible = false,
  onDismiss,
}: {
  variant?: Variant;
  title?: string;
  children?: ReactNode;
  dismissible?: boolean;
  onDismiss?: () => void;
}) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  function handleDismiss() {
    setDismissed(true);
    onDismiss?.();
  }

  return (
    <div
      role="alert"
      className={`mb-2.5 flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-[13px] leading-relaxed animate-[chipIn_260ms_spring] ${VARIANT_CLASSES[variant]}`}
    >
      <span className="mt-0.5 shrink-0">{ICONS[variant]}</span>
      <div className="flex-1">
        {title && <div className="mb-0.5 font-semibold">{title}</div>}
        {children}
      </div>
      {dismissible && (
        <button
          onClick={handleDismiss}
          aria-label="Dismiss"
          className="shrink-0 px-0.5 text-[14px] opacity-60 transition-opacity duration-fast hover:opacity-100"
        >
          &times;
        </button>
      )}
    </div>
  );
}
