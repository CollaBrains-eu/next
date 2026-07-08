interface BulkAction {
  label: string;
  onClick: () => void;
  variant?: "danger";
}

export function BulkActionBar({
  count,
  onCancel,
  actions,
}: {
  count: number;
  onCancel: () => void;
  actions: BulkAction[];
}) {
  if (count === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 z-[60] flex -translate-x-1/2 items-center gap-3.5 rounded-2xl bg-ink px-4 py-2.5 text-sm text-surface shadow-overlay">
      <span>
        <span className="font-bold">{count}</span> selected
      </span>
      <button onClick={onCancel} className="text-surface/80 hover:text-surface">
        Cancel
      </button>
      {actions.map((action) => (
        <button
          key={action.label}
          onClick={action.onClick}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors duration-fast ${
            action.variant === "danger" ? "bg-danger text-white hover:opacity-90" : "bg-white/10 text-surface hover:bg-white/20"
          }`}
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}
