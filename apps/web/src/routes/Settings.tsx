import { useEffect, useState } from "react";
import Card from "../components/Card";
import { Button } from "../components/ui/Button";
import { ApiError, getPreferences, setPreferences } from "../lib/api";

const LANGUAGE_OPTIONS = [
  { value: "", label: "No preference" },
  { value: "English", label: "English" },
  { value: "Nederlands", label: "Nederlands" },
  { value: "Deutsch", label: "Deutsch" },
];

export default function Settings() {
  const [language, setLanguage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPreferences()
      .then((prefs) => setLanguage(prefs.preferred_language ?? ""))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load preferences"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await setPreferences(language || null);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save preferences");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">Settings</h1>

      <Card className="flex max-w-md flex-col gap-3">
        <div>
          <label className="text-sm font-medium text-ink" htmlFor="preferred-language">
            Preferred language
          </label>
          <p className="text-xs text-ink-3">Used by AI Chat to respond in your preferred language.</p>
        </div>
        {loading ? (
          <p className="text-sm text-ink-3">Loading…</p>
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
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        {saved && <p className="text-sm text-success">Saved.</p>}
        <Button onClick={handleSave} disabled={loading || saving} className="self-start">
          Save
        </Button>
      </Card>
    </div>
  );
}
