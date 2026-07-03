import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { listDocuments, search as searchApi, type DocumentOut, type SearchResult } from "../lib/api";
import UploadDialog from "../components/UploadDialog";

const STATUS_STYLES: Record<string, string> = {
  ready: "bg-green-100 text-green-800",
  pending: "bg-slate-100 text-slate-700",
  ocr_processing: "bg-amber-100 text-amber-800",
  embedding: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700"}`}>
      {status}
    </span>
  );
}

export default function Workspace() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);

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

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Documents</h1>
        <UploadDialog onUploaded={refresh} />
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search documents…"
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={searching}
          className="rounded border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100 disabled:opacity-50"
        >
          Search
        </button>
        {results !== null && (
          <button
            type="button"
            onClick={() => {
              setResults(null);
              setQuery("");
            }}
            className="rounded px-3 py-2 text-sm text-slate-500 hover:text-slate-900"
          >
            Clear
          </button>
        )}
      </form>

      {results !== null ? (
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-medium text-slate-500">{results.length} result(s)</h2>
          {results.map((r) => (
            <Link
              key={r.chunk_id}
              to={`/documents/${r.document_id}`}
              className="block rounded border border-slate-200 bg-white p-4 hover:border-slate-400"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">{r.document_title}</span>
                <span className="text-xs text-slate-400">score {r.score.toFixed(3)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-sm text-slate-600">{r.content}</p>
            </Link>
          ))}
        </div>
      ) : loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : documents.length === 0 ? (
        <p className="text-slate-500">No documents yet. Upload one to get started.</p>
      ) : (
        <div className="flex flex-col divide-y divide-slate-200 rounded border border-slate-200 bg-white">
          {documents.map((doc) => (
            <Link
              key={doc.id}
              to={`/documents/${doc.id}`}
              className="flex items-center justify-between px-4 py-3 hover:bg-slate-50"
            >
              <div>
                <p className="font-medium">{doc.title}</p>
                <p className="text-xs text-slate-400">{new Date(doc.created_at).toLocaleString()}</p>
              </div>
              <StatusBadge status={doc.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
