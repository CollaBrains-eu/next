import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "./ui/Button";
import { Modal } from "./ui/Modal";

export function DeleteConfirmButton({
  confirmTitle,
  confirmBody,
  confirmLabel,
  onConfirm,
  deleting,
}: {
  confirmTitle: string;
  confirmBody: string;
  // Distinct from the trigger button's generic "Delete" label -- both
  // buttons are simultaneously in the DOM while the modal is open (Modal
  // doesn't unmount the trigger), so they need different accessible names.
  confirmLabel: string;
  onConfirm: () => void;
  deleting: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="danger" size="sm" onClick={() => setOpen(true)} disabled={deleting}>
        {t("common.delete")}
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title={confirmTitle}>
        <p className="mb-4 text-sm text-ink-2">{confirmBody}</p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="danger"
            size="sm"
            disabled={deleting}
            onClick={() => {
              setOpen(false);
              onConfirm();
            }}
          >
            {confirmLabel}
          </Button>
        </div>
      </Modal>
    </>
  );
}
