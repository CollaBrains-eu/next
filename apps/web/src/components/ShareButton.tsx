import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, createShareLink, type ShareLinkOut, type ShareableEntityType } from "../lib/api";
import { useDateFormat } from "../hooks/useDateFormat";
import { Button } from "./ui/Button";
import { Modal } from "./ui/Modal";

export function ShareButton({ entityType, entityId }: { entityType: ShareableEntityType; entityId: string }) {
  const { t } = useTranslation();
  const { formatDateTime } = useDateFormat();
  const [link, setLink] = useState<ShareLinkOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleShare() {
    setLoading(true);
    setError(null);
    try {
      setLink(await createShareLink(entityType, entityId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("share.createError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Button variant="secondary" size="sm" onClick={handleShare} disabled={loading}>
        {t("common.share")}
      </Button>
      <Modal open={!!link || !!error} onClose={() => { setLink(null); setError(null); }} title={t("share.modalTitle")}>
        {error && <p className="text-sm text-danger">{error}</p>}
        {link && (
          <div className="flex flex-col gap-2">
            <input
              readOnly
              value={link.url}
              onFocus={(event) => event.currentTarget.select()}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink"
            />
            <Button size="sm" onClick={() => navigator.clipboard.writeText(link.url)}>
              {t("share.copyLink")}
            </Button>
            <p className="text-xs text-ink-3">{t("share.expiresAt", { date: formatDateTime(link.expires_at) })}</p>
          </div>
        )}
      </Modal>
    </>
  );
}
