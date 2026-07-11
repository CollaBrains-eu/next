import type { ReactNode } from "react";

export interface MetadataItem {
  label: string;
  value: ReactNode;
}

/**
 * Reusable key/value block for entity metadata (status, dates, counts).
 * Replaces the ad hoc "·"-separated inline text a few detail pages used.
 */
export function MetadataList({ items }: { items: MetadataItem[] }) {
  return (
    <dl className="divide-y divide-dashed divide-edge">
      {items.map((item) => (
        <div key={item.label} className="flex items-center justify-between gap-3 py-1.5 text-[12.5px]">
          <dt className="text-ink-3">{item.label}</dt>
          <dd className="text-ink">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
