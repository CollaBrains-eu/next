import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { listEntities, type EntityOut } from "../lib/api";

const TYPE_STYLES: Record<string, string> = {
  person: "bg-blue-100 text-blue-800",
  organization: "bg-purple-100 text-purple-800",
  location: "bg-green-100 text-green-800",
  other: "bg-slate-100 text-slate-700",
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    listEntities(q || undefined, entityType || undefined)
      .then(setEntities)
      .finally(() => setLoading(false));
  }, [q, entityType]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold">Entities</h1>
        <p className="mt-1 text-sm text-slate-500">
          People, organizations, and locations extracted from your documents. Select one to explore its
          relationships.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search entities…"
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />
        <select
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        >
          <option value="">All types</option>
          <option value="person">Person</option>
          <option value="organization">Organization</option>
          <option value="location">Location</option>
          <option value="other">Other</option>
        </select>
      </form>

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : entities.length === 0 ? (
        <p className="text-slate-500">No entities found.</p>
      ) : (
        <div className="flex flex-col divide-y divide-slate-200 rounded border border-slate-200 bg-white">
          {entities.map((entity) => (
            <Link
              key={entity.id}
              to={`/entities/${entity.id}`}
              className="flex items-center justify-between px-4 py-3 hover:bg-slate-50"
            >
              <span className="text-sm font-medium">{entity.name}</span>
              <TypeBadge type={entity.entity_type} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
