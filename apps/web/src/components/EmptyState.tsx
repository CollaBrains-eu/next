import type { ReactNode } from "react";

export default function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded border border-dashed border-slate-300 px-6 py-12 text-center">
      <p className="text-sm text-slate-500">{message}</p>
      {action}
    </div>
  );
}
