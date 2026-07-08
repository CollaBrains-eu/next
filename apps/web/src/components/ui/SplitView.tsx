import type { ReactNode } from "react";

export function SplitView({
  enabled,
  list,
  detail,
}: {
  enabled: boolean;
  list: ReactNode;
  detail: ReactNode | null;
}) {
  if (!enabled) return <>{list}</>;

  return (
    <div className="flex gap-0 divide-x divide-edge">
      <div className="flex-1 overflow-y-auto pr-5">{list}</div>
      <div className="w-[260px] flex-shrink-0 overflow-y-auto pl-5">
        {detail ?? <p className="text-center text-sm text-ink-3">Select an item to preview it here</p>}
      </div>
    </div>
  );
}
