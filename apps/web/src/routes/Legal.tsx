import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError, legalDraft, listDocuments, type Citation, type DocumentOut } from "../lib/api";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Checkbox } from "../components/ui/form";
import { useLoadingBar } from "../lib/loadingBar";

export default function Legal() {
  const { t } = useTranslation();
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [instruction, setInstruction] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ draft: string; citations: Citation[]; disclaimer: string } | null>(null);
  const { start, done } = useLoadingBar();

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
    start();
    try {
      setResult(await legalDraft(instruction.trim(), Array.from(selectedIds)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("legal.loadError"));
    } finally {
      setDrafting(false);
      done();
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">{t("nav.legalDraft")}</h1>
        <p className="mt-1 text-sm text-ink-2">{t("legal.description")}</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm text-ink">
          {t("legal.instructionLabel")}
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            rows={4}
            placeholder={t("legal.instructionPlaceholder")}
            className="rounded-xl border border-edge bg-surface px-3 py-2 text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft"
          />
        </label>

        {documents.length > 0 && (
          <div>
            <p className="text-sm font-medium text-ink-2">{t("legal.scopeLabel")}</p>
            <div className="mt-1 flex flex-col gap-1 rounded-xl border border-edge bg-surface p-3 max-h-48 overflow-y-auto">
              {documents.map((doc) => (
                <Checkbox
                  key={doc.id}
                  label={doc.title}
                  checked={selectedIds.has(doc.id)}
                  onChange={() => toggleDocument(doc.id)}
                />
              ))}
            </div>
          </div>
        )}

        <Button type="submit" disabled={drafting || !instruction.trim()} className="self-start">
          {drafting ? t("legal.drafting") : t("legal.draftButton")}
        </Button>
        {error && <p className="text-sm text-danger">{error}</p>}
      </form>

      {result && (
        <div className="flex flex-col gap-3 rounded-2xl border border-edge bg-surface p-4">
          <Alert variant="warning">{result.disclaimer}</Alert>
          <p className="whitespace-pre-wrap text-sm text-ink">{result.draft}</p>
          {result.citations.length > 0 && (
            <div className="flex flex-wrap gap-2 border-t border-edge pt-2 text-xs text-ink-3">
              {result.citations.map((c) => (
                <Link key={c.chunk_id} to={`/documents/${c.document_id}`} className="hover:text-accent hover:underline">
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
