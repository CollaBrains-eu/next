import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, legalDraft, listDocuments, type Citation, type DocumentOut } from "../lib/api";

export default function Legal() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [instruction, setInstruction] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ draft: string; citations: Citation[]; disclaimer: string } | null>(null);

  useEffect(() => {
    listDocuments().then(setDocuments);
  }, []);

  function toggleDocument(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!instruction.trim() || drafting) return;
    setDrafting(true);
    setError(null);
    setResult(null);
    try {
      setResult(await legalDraft(instruction.trim(), Array.from(selectedIds)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Draft request failed");
    } finally {
      setDrafting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Legal Draft</h1>
        <p className="mt-1 text-sm text-slate-500">
          Drafts are grounded only in the documents you select (or all documents if none are selected) and are
          never a substitute for attorney review.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          Drafting instruction
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            rows={4}
            placeholder="e.g. Draft a letter summarizing the client's obligations under the attached agreement."
            className="rounded border border-slate-300 px-3 py-2 focus:border-slate-500 focus:outline-none"
          />
        </label>

        {documents.length > 0 && (
          <div>
            <p className="text-sm font-medium text-slate-700">Scope to documents (optional)</p>
            <div className="mt-1 flex flex-col gap-1 rounded border border-slate-200 bg-white p-3 max-h-48 overflow-y-auto">
              {documents.map((doc) => (
                <label key={doc.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(doc.id)}
                    onChange={() => toggleDocument(doc.id)}
                  />
                  {doc.title}
                </label>
              ))}
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={drafting || !instruction.trim()}
          className="self-start rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {drafting ? "Drafting…" : "Draft"}
        </button>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>

      {result && (
        <div className="flex flex-col gap-3 rounded border border-slate-200 bg-white p-4">
          <p className="rounded bg-amber-50 p-3 text-xs text-amber-800">{result.disclaimer}</p>
          <p className="whitespace-pre-wrap text-sm">{result.draft}</p>
          {result.citations.length > 0 && (
            <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-2 text-xs text-slate-500">
              {result.citations.map((c) => (
                <Link key={c.chunk_id} to={`/documents/${c.document_id}`} className="hover:text-slate-900 hover:underline">
                  [{c.marker}] {c.document_title}
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
