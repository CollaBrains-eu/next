import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { listEntities, type EntityOut } from "../lib/api";

const TYPE_STYLES: Record<string, string> = {
  person: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  organization: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  location: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  other: "bg-hover text-ink-2",
};

function TypeBadge({ type }: { type: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_STYLES[type] ?? TYPE_STYLES.other}`}>
      {type}
    </span>
  );
}

export default function Entities() {
  const { t } = useTranslation();
  const [entities, setEntities] = useState<EntityOut[]>([]);
  const [q, setQ] = useState("");
  const [entityType, setEntityType] = useState("");
  const [statusFilter, setStatusFilter] = useState("confirmed");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    listEntities(q || undefined, entityType || undefined, statusFilter)
      .then(setEntities)
      .finally(() => setLoading(false));
  }, [q, entityType, statusFilter]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-ink">{t("entities.title")}</h1>
        <p className="mt-1 text-sm text-ink-2">{t("entities.description")}</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <form onSubmit={handleSubmit} className="flex flex-wrap gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("entities.searchPlaceholder")}
            className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft sm:w-auto"
          />
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
          >
            <option value="">{t("entities.typeAll")}</option>
            <option value="person">{t("entities.typePerson")}</option>
            <option value="organization">{t("entities.typeOrganization")}</option>
            <option value="location">{t("entities.typeLocation")}</option>
            <option value="other">{t("entities.typeOther")}</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
          >
            <option value="confirmed">{t("entities.statusConfirmed")}</option>
            <option value="pending_review">{t("entities.statusPendingReview")}</option>
            <option value="rejected">{t("entities.statusRejected")}</option>
            <option value="all">{t("entities.statusAll")}</option>
          </select>
        </form>
        <Link to="/entities/review" className="shrink-0 text-sm text-accent hover:underline">
          {t("entities.reviewPending")}
        </Link>
      </div>

      {loading ? (
        <p className="text-ink-3">{t("common.loading")}</p>
      ) : entities.length === 0 ? (
        <p className="text-ink-3">{t("entities.emptyMessage")}</p>
      ) : (
        <div className="flex flex-col divide-y divide-edge rounded-2xl border border-edge bg-surface">
          {entities.map((entity) => (
            <Link
              key={entity.id}
              to={`/entities/${entity.id}`}
              className="flex items-center justify-between gap-3 px-4 py-3 transition-colors duration-fast hover:bg-hover"
            >
              <span className="min-w-0 truncate text-sm font-medium text-ink" title={entity.name}>
                {entity.name}
              </span>
              <TypeBadge type={entity.entity_type} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
