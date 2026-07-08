import type { ReactNode } from "react";

export default function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-2xl border border-edge bg-surface px-6 py-14 text-center">
      <div
        data-testid="empty-state-blob"
        className="h-16 w-16 animate-bounce rounded-full bg-accent-soft"
        style={{ animationDuration: "3s" }}
      />
      <p className="text-sm text-ink-2">{message}</p>
      {action}
    </div>
  );
}
