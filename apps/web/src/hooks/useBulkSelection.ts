import { useCallback, useState } from "react";

export function useBulkSelection<T>(getKey: (item: T) => string): {
  selectedKeys: Set<string>;
  isSelected: (item: T) => boolean;
  toggle: (item: T) => void;
  clear: () => void;
  selectedCount: number;
} {
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());

  const toggle = useCallback(
    (item: T) => {
      const key = getKey(item);
      setSelectedKeys((prev) => {
        const next = new Set(prev);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
      });
    },
    [getKey]
  );

  const isSelected = useCallback((item: T) => selectedKeys.has(getKey(item)), [selectedKeys, getKey]);

  const clear = useCallback(() => setSelectedKeys(new Set()), []);

  return { selectedKeys, isSelected, toggle, clear, selectedCount: selectedKeys.size };
}
