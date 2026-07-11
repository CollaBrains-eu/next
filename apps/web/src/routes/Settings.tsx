import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Card from "../components/Card";
import { Button } from "../components/ui/Button";
import { ApiError, getPreferences, setPreferences } from "../lib/api";
import { syncLanguage } from "../lib/auth";

export default function Settings() {
  const { t } = useTranslation();
  const [language, setLanguage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const languageOptions = [
    { value: "", label: t("settings.noPreference") },
    { value: "English", label: "English" },
    { value: "Nederlands", label: "Nederlands" },
    { value: "Deutsch", label: "Deutsch" },
  ];

  useEffect(() => {
    getPreferences()
      .then((prefs) => setLanguage(prefs.preferred_language ?? ""))
      .catch((err) => setError(err instanceof ApiError ? err.message : t("settings.loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await setPreferences(language || null);
      syncLanguage(language || null);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("settings.saveError"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">{t("settings.title")}</h1>

      <Card className="flex max-w-md flex-col gap-3">
        <div>
          <label className="text-sm font-medium text-ink" htmlFor="preferred-language">
            {t("settings.preferredLanguage")}
          </label>
          <p className="text-xs text-ink-3">{t("settings.preferredLanguageHint")}</p>
        </div>
        {loading ? (
          <p className="text-sm text-ink-3">{t("common.loading")}</p>
        ) : (
          <select
            id="preferred-language"
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value);
              setSaved(false);
            }}
            className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
          >
            {languageOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        {saved && <p className="text-sm text-success">{t("settings.saved")}</p>}
        <Button onClick={handleSave} disabled={loading || saving} className="self-start">
          {t("settings.save")}
        </Button>
      </Card>
    </div>
  );
}
