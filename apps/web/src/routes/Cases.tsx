import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { ApiError, createCase, listCases, type CaseOut } from "../lib/api";

export default function Cases() {
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
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load cases"))
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
      setError(err instanceof ApiError ? err.message : "Failed to create case");
    } finally {
      setSubmitting(false);
    }
  }

  const newCaseButton = !creating && (
    <button
      onClick={() => setCreating(true)}
      className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
    >
      New case
    </button>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Cases</h1>
        {cases.length > 0 && newCaseButton}
      </div>

      {creating && (
        <Card>
          <form onSubmit={handleCreate} className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">New case</span>
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="text-sm text-slate-500 hover:text-slate-900"
              >
                Cancel
              </button>
            </div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Case name"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              rows={2}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={submitting || !name.trim()}
              className="self-start rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            >
              Create
            </button>
          </form>
        </Card>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : cases.length === 0 && !creating ? (
        <EmptyState message="No cases yet." action={newCaseButton} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {cases.map((c) => (
            <Link key={c.id} to={`/cases/${c.id}`}>
              <Card className="flex h-full flex-col gap-2 hover:border-slate-400">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{c.name}</span>
                  <span
                    className={`rounded px-2 py-0.5 text-xs ${
                      c.status === "open" ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {c.status}
                  </span>
                </div>
                {c.description && <p className="text-sm text-slate-500">{c.description}</p>}
                <span className="mt-auto text-xs text-slate-400">
                  {new Date(c.created_at).toLocaleDateString()}
                </span>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
