import type { HTMLAttributes } from "react";

type Variant = "default" | "success" | "warning" | "danger";

const VARIANT_CLASSES: Record<Variant, string> = {
  default: "bg-accent-soft text-accent",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
};

export function Badge({
  variant = "default",
  pulsing = false,
  ready = false,
  className = "",
  children,
  ...rest
}: {
  variant?: Variant;
  pulsing?: boolean;
  ready?: boolean;
} & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    >
      {ready ? (
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
          <path d="M3 8l3.5 3.5L13 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <span className={`h-1.5 w-1.5 rounded-full bg-current ${pulsing ? "animate-pulse" : ""}`} />
      )}
      {children}
    </span>
  );
}
