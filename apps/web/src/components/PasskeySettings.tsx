import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Card from "./Card";
import EmptyState from "./EmptyState";
import { Button } from "./ui/Button";
import { ApiError, deleteWebauthnCredential, listWebauthnCredentials, type WebauthnCredentialOut } from "../lib/api";
import { isPasskeySupported, registerPasskey } from "../lib/webauthn";
import { useDateFormat } from "../hooks/useDateFormat";

export function PasskeySettings() {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
  const [credentials, setCredentials] = useState<WebauthnCredentialOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [registering, setRegistering] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  function load() {
    listWebauthnCredentials()
      .then(setCredentials)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("passkeys.loadError")));
  }

  useEffect(load, [t]);

  async function handleRegister() {
    setError(null);
    setRegistering(true);
    try {
      const label = window.prompt(t("passkeys.labelPrompt")) || undefined;
      await registerPasskey(label);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("passkeys.registerError"));
    } finally {
      setRegistering(false);
    }
  }

  async function handleDelete(id: string) {
    setBusyId(id);
    try {
      await deleteWebauthnCredential(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("passkeys.actionError"));
    } finally {
      setBusyId(null);
    }
  }

  if (!isPasskeySupported()) return null;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">{t("passkeys.title")}</h2>
          <p className="text-xs text-ink-3">{t("passkeys.description")}</p>
        </div>
        <Button variant="secondary" size="sm" onClick={handleRegister} disabled={registering}>
          {registering ? t("passkeys.registering") : t("passkeys.addPasskey")}
        </Button>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {credentials === null ? (
        <p className="text-sm text-ink-3">{t("common.loading")}</p>
      ) : credentials.length === 0 ? (
        <EmptyState message={t("passkeys.empty")} />
      ) : (
        <div className="flex flex-col gap-2">
          {credentials.map((credential) => (
            <Card key={credential.id} className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium text-ink">{credential.label || t("passkeys.unnamedPasskey")}</p>
                <p className="text-xs text-ink-3">
                  {t("passkeys.createdAt", { date: formatDate(credential.created_at) })}
                  {credential.last_used_at && ` · ${t("passkeys.lastUsed", { date: formatDate(credential.last_used_at) })}`}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                disabled={busyId === credential.id}
                onClick={() => handleDelete(credential.id)}
              >
                {t("passkeys.remove")}
              </Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
