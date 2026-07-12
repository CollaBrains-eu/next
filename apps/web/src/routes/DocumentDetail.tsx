import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError, deleteDocument, getDocument, reprocessDocument, summarizeDocument, type DocumentDetailOut } from "../lib/api";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Breadcrumbs } from "../components/ui/Breadcrumbs";
import Card from "../components/Card";
import { Button } from "../components/ui/Button";
import { MetadataList } from "../components/ui/MetadataList";
import { Modal } from "../components/ui/Modal";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "default"> = {
  ready: "success",
  pending: "default",
  ocr_processing: "warning",
  embedding: "warning",
  failed: "danger",
};

export default function DocumentDetail() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { user } = useAuth();
  const [doc, setDoc] = useState<DocumentDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    getDocument(id)
      .then(setDoc)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("documentDetail.loadError")));
  }, [id, t]);

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
      setError(err instanceof ApiError ? err.message : t("documentDetail.summarizeError"));
    } finally {
      setSummarizing(false);
    }
  }

  async function handleReprocess() {
    if (!id) return;
    setReprocessing(true);
    try {
      await reprocessDocument(id);
      showToast(t("documentDetail.reprocessQueued"));
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("documentDetail.reprocessError"));
    } finally {
      setReprocessing(false);
    }
  }

  async function handleConfirmDelete() {
    if (!id) return;
    setDeleting(true);
    try {
      await deleteDocument(id);
      setConfirmOpen(false);
      showToast(t("documentDetail.deletedToast", { title: doc?.title }));
      navigate("/documents");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("documentDetail.deleteError"));
      setConfirmOpen(false);
      setDeleting(false);
    }
  }

  if (error) {
    return (
      <div>
        <Breadcrumbs items={[{ label: t("nav.documents"), to: "/documents" }, { label: t("documentDetail.breadcrumbError") }]} />
        <Alert variant="danger" title={t("documentDetail.loadError")}>
          {error}
        </Alert>
      </div>
    );
  }

  if (!doc) return <p className="text-ink-2">{t("common.loading")}</p>;

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: t("nav.documents"), to: "/documents" }, { label: doc.title }]} />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold text-ink">{doc.title}</h1>
          <div className="mt-2 max-w-xs">
            <MetadataList
              items={[
                { label: t("documentDetail.metaType"), value: doc.mime_type },
                {
                  label: t("documents.columnStatus"),
                  value: <Badge variant={STATUS_VARIANT[doc.status] ?? "default"}>{doc.status}</Badge>,
                },
                { label: t("documentDetail.metaChunks"), value: doc.chunk_count },
              ]}
            />
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="secondary" size="sm" onClick={handleSummarize} disabled={doc.status !== "ready" || summarizing}>
            {summarizing ? t("documentDetail.summarizing") : doc.summary ? t("documentDetail.resummarize") : t("documentDetail.summarize")}
          </Button>
          {user?.role === "admin" && doc.status === "failed" && (
            <Button variant="secondary" size="sm" onClick={handleReprocess} disabled={reprocessing}>
              {reprocessing ? t("documentDetail.reprocessing") : t("documentDetail.reprocess")}
            </Button>
          )}
          <Button variant="danger" size="sm" onClick={() => setConfirmOpen(true)} disabled={deleting}>
            {t("common.delete")}
          </Button>
        </div>
      </div>

      {doc.error && (
        <Alert variant="danger" title={t("documentDetail.processingError")}>
          {doc.error}
        </Alert>
      )}

      {doc.summary && (
        <Card>
          <h2 className="text-sm font-medium text-ink-2">{t("documentDetail.summary")}</h2>
          <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{doc.summary}</p>
        </Card>
      )}

      {doc.ocr_text && (
        <Card>
          <h2 className="text-sm font-medium text-ink-2">{t("documentDetail.extractedText")}</h2>
          <p className="mt-1 max-h-96 overflow-y-auto whitespace-pre-wrap text-sm text-ink">{doc.ocr_text}</p>
        </Card>
      )}

      <Modal open={confirmOpen} onClose={() => setConfirmOpen(false)} title={t("documentDetail.deleteModalTitle", { title: doc.title })}>
        <p className="mb-4 text-sm text-ink-2">{t("documentDetail.deleteModalBody")}</p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => setConfirmOpen(false)}>
            {t("common.cancel")}
          </Button>
          <Button variant="danger" size="sm" onClick={handleConfirmDelete} disabled={deleting}>
            {t("documentDetail.deleteConfirm")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
