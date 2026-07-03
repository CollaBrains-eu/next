import { useRef, useState } from "react";
import { ApiError, uploadDocument } from "../lib/api";

export default function UploadDialog({ onUploaded }: { onUploaded: () => void }) {
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
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
      >
        Upload document
      </button>
    );
  }

  return (
    <div className="rounded border border-slate-300 bg-white p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Upload a document</span>
        <button onClick={() => setOpen(false)} className="text-sm text-slate-500 hover:text-slate-900">
          Cancel
        </button>
      </div>
      <input
        ref={inputRef}
        type="file"
        className="mt-3 block text-sm"
        disabled={uploading}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />
      {uploading && <p className="mt-2 text-sm text-slate-500">Uploading…</p>}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
