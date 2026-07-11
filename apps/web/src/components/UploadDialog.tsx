import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, uploadDocument } from "../lib/api";
import { Button } from "./ui/Button";

export default function UploadDialog({ onUploaded }: { onUploaded: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(file);
      setOpen(false);
      onUploaded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("documents.uploadError"));
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  if (!open) {
    return <Button onClick={() => setOpen(true)}>{t("documents.uploadButton")}</Button>;
  }

  return (
    <div className="rounded-2xl border border-edge bg-surface p-4 shadow-raised">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-ink">{t("documents.uploadTitle")}</span>
        <button
          onClick={() => setOpen(false)}
          className="text-sm text-ink-2 transition-colors duration-fast hover:text-ink"
        >
          {t("common.cancel")}
        </button>
      </div>
      <input
        ref={inputRef}
        type="file"
        className="mt-3 block text-sm text-ink"
        disabled={uploading}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />
      {uploading && <p className="mt-2 text-sm text-ink-2">{t("documents.uploading")}</p>}
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
    </div>
  );
}
