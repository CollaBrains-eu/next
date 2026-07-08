import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { listDocuments, search as searchApi, deleteDocument, type DocumentOut, type SearchResult } from "../lib/api";
import UploadDialog from "../components/UploadDialog";
import { DataTable, type Column } from "../components/ui/DataTable";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/form";
import EmptyState from "../components/EmptyState";
import { useBulkSelection } from "../hooks/useBulkSelection";
import { BulkActionBar } from "../components/ui/BulkActionBar";
import { FilterChips } from "../components/ui/FilterChips";
import { useToast } from "../lib/toast";

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "default"> = {
  ready: "success",
  pending: "default",
  ocr_processing: "warning",
  embedding: "warning",
  failed: "danger",
};

const STATUS_FILTER_OPTIONS = [
  { id: "ready", label: "Status: Ready" },
  { id: "failed", label: "Status: Failed" },
  { id: "pending", label: "Status: Pending" },
];

export default function Workspace() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [statusFilters, setStatusFilters] = useState<string[]>([]);
  const { isSelected, toggle, clear, selectedCount, selectedKeys } = useBulkSelection<DocumentOut>((doc) => doc.id);
  const { showToast } = useToast();

  const refresh = useCallback((showLoading = false) => {
    if (showLoading) setLoading(true);
    listDocuments()
      .then(setDocuments)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh(true);
    const interval = setInterval(() => refresh(false), 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    if (!query.trim()) {
      setResults(null);
      return;
    }
    setSearching(true);
    try {
      setResults(await searchApi(query.trim()));
    } finally {
      setSearching(false);
    }
  }

  async function handleBulkDelete() {
    const ids = [...selectedKeys];
    await Promise.all(ids.map((id) => deleteDocument(id)));
    clear();
    refresh();
    showToast(`${ids.length} document${ids.length === 1 ? "" : "s"} deleted`);
  }

  const activeFilters = useMemo(() => new Set(statusFilters), [statusFilters]);
  const filteredDocuments = useMemo(
    () => (activeFilters.size === 0 ? documents : documents.filter((doc) => activeFilters.has(doc.status))),
    [documents, activeFilters]
  );

  const columns: Column<DocumentOut>[] = [
    {
      key: "select",
      header: "",
      render: (doc) => (
        <input
          type="checkbox"
          checked={isSelected(doc)}
          onChange={() => toggle(doc)}
          onClick={(event) => event.stopPropagation()}
          className="h-4 w-4 accent-accent"
        />
      ),
    },
    {
      key: "title",
      header: "Title",
      sortable: true,
      sortValue: (doc) => doc.title.toLowerCase(),
      render: (doc) => (
        <Link to={`/documents/${doc.id}`} className="font-medium text-ink hover:text-accent">
          {doc.title}
        </Link>
      ),
    },
    {
      key: "created_at",
      header: "Uploaded",
      sortable: true,
      sortValue: (doc) => doc.created_at,
      render: (doc) => new Date(doc.created_at).toLocaleString(),
    },
    {
      key: "status",
      header: "Status",
      render: (doc) => <Badge variant={STATUS_VARIANT[doc.status] ?? "default"}>{doc.status}</Badge>,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">Documents</h1>
        <UploadDialog onUploaded={refresh} />
      </div>

      <form onSubmit={handleSearch} className="flex items-end gap-2">
        <div className="flex-1">
          <TextField label="Search" value={query} onChange={setQuery} placeholder="Search documents…" />
        </div>
        <Button type="submit" variant="secondary" disabled={searching}>
          Search
        </Button>
        {results !== null && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setResults(null);
              setQuery("");
            }}
          >
            Clear
          </Button>
        )}
      </form>

      {results !== null ? (
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-medium text-ink-2">{results.length} result(s)</h2>
          {results.map((r) => (
            <Link
              key={r.chunk_id}
              to={`/documents/${r.document_id}`}
              className="block rounded-2xl border border-edge bg-surface p-4 shadow-raised hover:border-accent"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-ink">{r.document_title}</span>
                <span className="text-xs text-ink-3">score {r.score.toFixed(3)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-sm text-ink-2">{r.content}</p>
            </Link>
          ))}
        </div>
      ) : loading ? (
        <p className="text-ink-2">Loading…</p>
      ) : documents.length === 0 ? (
        <EmptyState message="No documents yet. Upload one to get started." />
      ) : (
        <>
          <FilterChips
            chips={STATUS_FILTER_OPTIONS.filter((opt) => statusFilters.includes(opt.id))}
            onRemove={(id) => setStatusFilters((prev) => prev.filter((s) => s !== id))}
            addOptions={STATUS_FILTER_OPTIONS.filter((opt) => !statusFilters.includes(opt.id))}
            onAdd={(opt) => setStatusFilters((prev) => [...prev, opt.id])}
          />
          <DataTable columns={columns} rows={filteredDocuments} rowKey={(doc) => doc.id} />
          <BulkActionBar
            count={selectedCount}
            onCancel={clear}
            actions={[{ label: "Delete", onClick: handleBulkDelete, variant: "danger" }]}
          />
        </>
      )}
    </div>
  );
}
