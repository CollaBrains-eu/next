import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { ApiError, createCase, listCases, type CaseOut } from "../lib/api";
import { useDateFormat } from "../hooks/useDateFormat";

export default function Cases() {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
  const [cases, setCases] = useState<CaseOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function refresh() {
    setLoading(true);
    listCases()
      .then(setCases)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("cases.loadError")))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await createCase(name.trim(), description.trim() || undefined);
      setName("");
      setDescription("");
      setCreating(false);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("cases.createError"));
    } finally {
      setSubmitting(false);
    }
  }

  const newCaseButton = !creating && (
    <Button onClick={() => setCreating(true)}>{t("cases.newCase")}</Button>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">{t("cases.title")}</h1>
        {cases.length > 0 && newCaseButton}
      </div>

      {creating && (
        <Card>
          <form onSubmit={handleCreate} className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-ink">{t("cases.newCase")}</span>
              <Button type="button" variant="ghost" size="sm" onClick={() => setCreating(false)}>
                {t("common.cancel")}
              </Button>
            </div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("cases.namePlaceholder")}
              className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("cases.descriptionPlaceholder")}
              rows={2}
              className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft"
            />
            <Button type="submit" disabled={submitting || !name.trim()} className="self-start">
              {t("common.create")}
            </Button>
          </form>
        </Card>
      )}

      {error && <p className="text-sm text-danger">{error}</p>}

      {loading ? (
        <p className="text-ink-3">{t("common.loading")}</p>
      ) : cases.length === 0 && !creating ? (
        <EmptyState message={t("cases.emptyMessage")} action={newCaseButton} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {cases.map((c) => (
            <Link key={c.id} to={`/cases/${c.id}`}>
              <Card className="flex h-full flex-col gap-2 transition-colors duration-fast hover:border-accent">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-ink">{c.name}</span>
                  <Badge variant={c.status === "open" ? "success" : "default"}>{c.status}</Badge>
                </div>
                {c.description && <p className="text-sm text-ink-2">{c.description}</p>}
                <span className="mt-auto text-xs text-ink-3">
                  {formatDate(c.created_at)}
                </span>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
