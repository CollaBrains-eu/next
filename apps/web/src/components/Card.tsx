import type { ReactNode } from "react";

export default function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded border border-slate-200 bg-white p-4 ${className}`}>{children}</div>;
}
