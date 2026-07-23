import { cloneElement, isValidElement, useId, type ReactNode } from "react";

export function Tooltip({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  const tooltipId = useId();
  // Wires aria-describedby onto the trigger when it's a single real element
  // (every current usage is exactly one button/icon) so screen readers
  // announce the label; falls back to rendering children as-is otherwise
  // rather than crashing on an unexpected shape.
  const trigger = isValidElement<{ "aria-describedby"?: string }>(children)
    ? cloneElement(children, { "aria-describedby": tooltipId })
    : children;

  return (
    <span className={`group relative inline-flex ${className}`}>
      {trigger}
      <span
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 translate-y-1 whitespace-nowrap rounded-lg bg-ink px-2.5 py-1 text-[11px] text-surface opacity-0 transition-all duration-fast ease-out-token group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:translate-y-0 group-focus-within:opacity-100"
      >
        {label}
      </span>
    </span>
  );
}
