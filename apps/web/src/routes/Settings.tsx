import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AddressHistory } from "../components/AddressHistory";
import Card from "../components/Card";
import { PasskeySettings } from "../components/PasskeySettings";
import { Button } from "../components/ui/Button";
import { ApiError, getPreferences, setPreferences } from "../lib/api";
import { syncLanguage } from "../lib/auth";
import { toDateFormatPrefs, type DateFormat, type TimeFormat } from "../lib/dateFormat";
import { setDateFormatPrefs } from "../hooks/useDateFormat";

export default function Settings() {
  const { t } = useTranslation();
  const [language, setLanguage] = useState("");
  const [dateFormat, setDateFormat] = useState<DateFormat>("eu");
  const [timeFormat, setTimeFormat] = useState<TimeFormat>("h24");
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

  const dateFormatOptions: { value: DateFormat; label: string }[] = [
    { value: "eu", label: t("settings.dateFormatEu") },
    { value: "us", label: t("settings.dateFormatUs") },
    { value: "iso", label: t("settings.dateFormatIso") },
  ];

  const timeFormatOptions: { value: TimeFormat; label: string }[] = [
    { value: "h24", label: t("settings.timeFormatH24") },
    { value: "h12", label: t("settings.timeFormatH12") },
  ];

  useEffect(() => {
    getPreferences()
      .then((prefs) => {
        setLanguage(prefs.preferred_language ?? "");
        const parsed = toDateFormatPrefs(prefs.date_format, prefs.time_format);
        setDateFormat(parsed.dateFormat);
        setTimeFormat(parsed.timeFormat);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : t("settings.loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await setPreferences({ preferredLanguage: language || null, dateFormat, timeFormat });
      syncLanguage(language || null);
      setDateFormatPrefs({ dateFormat, timeFormat });
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
          <>
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

            <div>
              <label className="text-sm font-medium text-ink" htmlFor="date-format">
                {t("settings.dateFormat")}
              </label>
              <select
                id="date-format"
                value={dateFormat}
                onChange={(e) => {
                  setDateFormat(e.target.value as DateFormat);
                  setSaved(false);
                }}
                className="mt-1 w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
              >
                {dateFormatOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm font-medium text-ink" htmlFor="time-format">
                {t("settings.timeFormat")}
              </label>
              <select
                id="time-format"
                value={timeFormat}
                onChange={(e) => {
                  setTimeFormat(e.target.value as TimeFormat);
                  setSaved(false);
                }}
                className="mt-1 w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
              >
                {timeFormatOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        {saved && <p className="text-sm text-success">{t("settings.saved")}</p>}
        <Button onClick={handleSave} disabled={loading || saving} className="self-start">
          {t("settings.save")}
        </Button>
      </Card>

      <PasskeySettings />

      <div className="flex flex-col gap-2">
        <div>
          <h2 className="text-lg font-semibold text-ink">{t("addressHistory.title")}</h2>
          <p className="text-xs text-ink-3">{t("addressHistory.description")}</p>
        </div>
        <AddressHistory />
      </div>
    </div>
  );
}
