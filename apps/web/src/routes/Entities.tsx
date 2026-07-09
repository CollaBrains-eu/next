import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
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
        <h1 className="text-2xl font-semibold text-ink">Entities</h1>
        <p className="mt-1 text-sm text-ink-2">
          People, organizations, and locations extracted from your documents. Select one to explore its
          relationships.
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <form onSubmit={handleSubmit} className="flex flex-wrap gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search entities…"
            className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft sm:w-auto"
          />
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
          >
            <option value="">All types</option>
            <option value="person">Person</option>
            <option value="organization">Organization</option>
            <option value="location">Location</option>
            <option value="other">Other</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
          >
            <option value="confirmed">Confirmed</option>
            <option value="pending_review">Pending review</option>
            <option value="rejected">Rejected</option>
            <option value="all">All</option>
          </select>
        </form>
        <Link to="/entities/review" className="shrink-0 text-sm text-accent hover:underline">
          Review pending →
        </Link>
      </div>

      {loading ? (
        <p className="text-ink-3">Loading…</p>
      ) : entities.length === 0 ? (
        <p className="text-ink-3">No entities found.</p>
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
