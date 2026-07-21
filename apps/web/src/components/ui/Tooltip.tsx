import type { ReactNode } from "react";

export function Tooltip({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <span className={`group relative inline-flex ${className}`}>
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 translate-y-1 whitespace-nowrap rounded-lg bg-ink px-2.5 py-1 text-[11px] text-surface opacity-0 transition-all duration-fast ease-out-token group-hover:translate-y-0 group-hover:opacity-100">
        {label}
      </span>
    </span>
  );
}
