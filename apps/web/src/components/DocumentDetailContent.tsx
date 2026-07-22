import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  downloadDocumentFile,
  downloadMetafieldIcs,
  previewDocumentFile,
  reprocessDocument,
  summarizeDocument,
  type DocumentDetailOut,
} from "../lib/api";
import { Alert } from "./ui/Alert";
import { Badge } from "./ui/Badge";
import Card from "./Card";
import { Button } from "./ui/Button";
import { MetadataList } from "./ui/MetadataList";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "default"> = {
  ready: "success",
  pending: "default",
  ocr_processing: "warning",
  embedding: "warning",
  failed: "danger",
};

const PREVIEWABLE_MIME_PREFIXES = ["application/pdf", "image/"];

function isPreviewable(mimeType: string): boolean {
  return PREVIEWABLE_MIME_PREFIXES.some((prefix) => mimeType.startsWith(prefix));
}

function formatCorrespondentAddress(doc: DocumentDetailOut): string | null {
  const streetLine = [doc.correspondent_street, doc.correspondent_house_number].filter(Boolean).join(" ");
  const poBoxLine = doc.correspondent_po_box ? `P.O. Box ${doc.correspondent_po_box}` : null;
  const cityLine = [doc.correspondent_postal_code, doc.correspondent_city].filter(Boolean).join(" ");
  const lines = [streetLine, poBoxLine, cityLine, doc.correspondent_country].filter(
    (line): line is string => Boolean(line),
  );
  return lines.length > 0 ? lines.join(", ") : null;
}

function humanizeFieldKey(key: string): string {
  return key
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function isDateLikeKey(key: string): boolean {
  return key.endsWith("_date");
}

export function DocumentDetailContent({
  document: doc,
  onChanged,
}: {
  document: DocumentDetailOut;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { user } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [previewing, setPreviewing] = useState(false);

  async function handleSummarize() {
    setSummarizing(true);
    try {
      await summarizeDocument(doc.id);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("documentDetail.summarizeError"));
    } finally {
      setSummarizing(false);
    }
  }

  async function handleReprocess() {
    setReprocessing(true);
    try {
      await reprocessDocument(doc.id);
      showToast(t("documentDetail.reprocessQueued"));
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("documentDetail.reprocessError"));
    } finally {
      setReprocessing(false);
    }
  }

  async function handleDownload() {
    setDownloading(true);
    try {
      await downloadDocumentFile(doc.id, doc.filename);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("documentDetail.downloadError"));
    } finally {
      setDownloading(false);
    }
  }

  async function handlePreview() {
    setPreviewing(true);
    try {
      await previewDocumentFile(doc.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("documentDetail.downloadError"));
    } finally {
      setPreviewing(false);
    }
  }

  async function handleDownloadMetafieldIcs(fieldKey: string) {
    const slug = `${doc.title}-${fieldKey}`
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
    try {
      await downloadMetafieldIcs(doc.id, fieldKey, `${slug || "event"}.ics`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("documentDetail.downloadError"));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <Alert variant="danger" title={t("documentDetail.loadError")}>
          {error}
        </Alert>
      )}

      <div className="max-w-xs">
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

      <div className="flex flex-wrap gap-2">
        {isPreviewable(doc.mime_type) && (
          <Button variant="secondary" size="sm" onClick={handlePreview} disabled={doc.status !== "ready" || previewing}>
            {t("documentDetail.preview")}
          </Button>
        )}
        <Button variant="secondary" size="sm" onClick={handleDownload} disabled={doc.status !== "ready" || downloading}>
          {t("documentDetail.download")}
        </Button>
        <Button variant="secondary" size="sm" onClick={handleSummarize} disabled={doc.status !== "ready" || summarizing}>
          {summarizing ? t("documentDetail.summarizing") : doc.summary ? t("documentDetail.resummarize") : t("documentDetail.summarize")}
        </Button>
        {user?.role === "admin" && doc.status === "failed" && (
          <Button variant="secondary" size="sm" onClick={handleReprocess} disabled={reprocessing}>
            {reprocessing ? t("documentDetail.reprocessing") : t("documentDetail.reprocess")}
          </Button>
        )}
      </div>

      {doc.error && (
        <Alert variant="danger" title={t("documentDetail.processingError")}>
          {doc.error}
        </Alert>
      )}

      {(doc.doc_type || doc.tags.length > 0 || doc.correspondent) && (
        <Card>
          <h2 className="text-sm font-medium text-ink-2">{t("documentDetail.classification")}</h2>
          <div className="mt-2 flex flex-col gap-2">
            {doc.doc_type && (
              <MetadataList items={[{ label: t("documentDetail.docType"), value: doc.doc_type }]} />
            )}
            {doc.tags.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-ink-3">{t("documentDetail.tags")}:</span>
                {doc.tags.map((tag) => (
                  <Badge key={tag} variant="default">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
            {doc.correspondent && (
              <div>
                <span className="text-xs text-ink-3">{t("documentDetail.correspondent")}:</span>
                <p className="text-sm text-ink">{doc.correspondent}</p>
                {formatCorrespondentAddress(doc) && (
                  <p className="text-sm text-ink-2">{formatCorrespondentAddress(doc)}</p>
                )}
              </div>
            )}
          </div>
        </Card>
      )}

      {doc.metafields && Object.keys(doc.metafields).length > 0 && (
        <Card>
          <h2 className="text-sm font-medium text-ink-2">{t("documentDetail.metafields")}</h2>
          <div className="mt-2 flex flex-col gap-2">
            {Object.entries(doc.metafields).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between gap-2 text-sm">
                <span className="text-ink-3">{humanizeFieldKey(key)}</span>
                <div className="flex items-center gap-2">
                  <span className="text-ink">{value}</span>
                  {isDateLikeKey(key) && (
                    <Button variant="ghost" size="sm" onClick={() => handleDownloadMetafieldIcs(key)}>
                      {t("documentDetail.addToCalendar")}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
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
    </div>
  );
}
