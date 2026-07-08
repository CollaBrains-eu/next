import { useMemo, useState } from "react";

export interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  sortValue?: (row: T) => string | number;
  render: (row: T) => React.ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  pageSize = 10,
  rowKey,
}: {
  columns: Column<T>[];
  rows: T[];
  pageSize?: number;
  rowKey: (row: T) => string;
}) {
  const [sort, setSort] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);
  const [page, setPage] = useState(1);

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return rows;
    const sorted = [...rows].sort((a, b) => {
      const va = column.sortValue!(a);
      const vb = column.sortValue!(b);
      if (va < vb) return sort.direction === "asc" ? -1 : 1;
      if (va > vb) return sort.direction === "asc" ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [rows, sort, columns]);

  const totalPages = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  const pageRows = sortedRows.slice((page - 1) * pageSize, page * pageSize);

  function handleSort(column: Column<T>) {
    if (!column.sortable) return;
    setSort((prev) => {
      if (prev?.key !== column.key) return { key: column.key, direction: "asc" };
      return { key: column.key, direction: prev.direction === "asc" ? "desc" : "asc" };
    });
    setPage(1);
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-edge bg-surface shadow-raised">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                onClick={() => handleSort(column)}
                className={`border-b border-edge px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-3 ${
                  column.sortable ? "cursor-pointer select-none hover:text-ink" : ""
                }`}
              >
                {column.header}
                {sort?.key === column.key && <span className="ml-1">{sort.direction === "asc" ? "▲" : "▼"}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pageRows.map((row) => (
            <tr key={rowKey(row)} className="transition-colors duration-fast hover:bg-hover">
              {columns.map((column) => (
                <td key={column.key} className="border-b border-edge px-4 py-2.5 tabular-nums last:border-b-0">
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 py-3">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              className={`h-7 w-7 rounded-lg text-xs transition-colors duration-fast ${
                p === page ? "bg-accent text-white" : "text-ink-2 hover:bg-hover"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
