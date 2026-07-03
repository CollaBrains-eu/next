import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, deleteDocument, getDocument, summarizeDocument, type DocumentDetailOut } from "../lib/api";

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<DocumentDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    getDocument(id)
      .then(setDoc)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load document"));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (doc && (doc.status === "pending" || doc.status === "processing")) {
      const interval = setInterval(load, 3000);
      return () => clearInterval(interval);
    }
  }, [doc, load]);

  async function handleSummarize() {
    if (!id) return;
    setSummarizing(true);
    try {
      await summarizeDocument(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Summarize failed");
    } finally {
      setSummarizing(false);
    }
  }

  async function handleDelete() {
    if (!id || !window.confirm("Delete this document? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await deleteDocument(id);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
      setDeleting(false);
    }
  }

  if (error) {
    return (
      <div>
        <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">
          ← Back
        </Link>
        <p className="mt-4 text-red-600">{error}</p>
      </div>
    );
  }

  if (!doc) return <p className="text-slate-500">Loading…</p>;

  return (
    <div className="flex flex-col gap-4">
      <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">
        ← Back
      </Link>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{doc.title}</h1>
          <p className="text-sm text-slate-500">
            {doc.mime_type} · {doc.status} · {doc.chunk_count} chunk(s)
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSummarize}
            disabled={doc.status !== "ready" || summarizing}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100 disabled:opacity-50"
          >
            {summarizing ? "Summarizing…" : doc.summary ? "Re-summarize" : "Summarize"}
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="rounded border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </div>

      {doc.error && (
        <p className="rounded bg-red-50 p-3 text-sm text-red-700">Processing error: {doc.error}</p>
      )}

      {doc.summary && (
        <div className="rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-medium text-slate-500">Summary</h2>
          <p className="mt-1 whitespace-pre-wrap text-sm">{doc.summary}</p>
        </div>
      )}

      {doc.ocr_text && (
        <div className="rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-medium text-slate-500">Extracted text</h2>
          <p className="mt-1 max-h-96 overflow-y-auto whitespace-pre-wrap text-sm text-slate-700">{doc.ocr_text}</p>
        </div>
      )}
    </div>
  );
}
