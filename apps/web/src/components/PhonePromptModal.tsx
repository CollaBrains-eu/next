import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, dismissPhonePrompt, linkPhoneNumber } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button } from "./ui/Button";
import { Modal } from "./ui/Modal";
import { TextField } from "./ui/form";

export function PhonePromptModal() {
  const { t } = useTranslation();
  const { user, refreshUser } = useAuth();
  const [phoneNumber, setPhoneNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const shouldShow = !!user && !user.phone_number && !user.phone_prompt_dismissed;
  if (!shouldShow) return null;

  async function handleSetPhone() {
    setSubmitting(true);
    setError(null);
    try {
      await linkPhoneNumber(phoneNumber);
      await refreshUser();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("phonePrompt.error"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSkip() {
    setSubmitting(true);
    try {
      await dismissPhonePrompt();
      await refreshUser();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open onClose={handleSkip} title={t("phonePrompt.title")}>
      <div className="flex flex-col gap-3">
        <p className="text-sm text-ink-2">{t("phonePrompt.description")}</p>
        <TextField
          label={t("phonePrompt.phoneLabel")}
          value={phoneNumber}
          onChange={setPhoneNumber}
          placeholder="+491511234567"
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={handleSkip} disabled={submitting}>
            {t("phonePrompt.skip")}
          </Button>
          <Button type="button" size="sm" onClick={handleSetPhone} disabled={submitting || !phoneNumber.trim()}>
            {t("phonePrompt.setPhone")}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
