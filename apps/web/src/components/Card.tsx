import type { ReactNode } from "react";

export default function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-edge bg-surface p-4 shadow-raised ${className}`}>{children}</div>
  );
}
