import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Card from "../components/Card";
import {
  ApiError,
  attachDocumentToCase,
  getCase,
  linkDecisionToCase,
  linkTaskToCase,
  linkVehicleToCase,
  listDecisions,
  listDocuments,
  listTasks,
  listVehicles,
  updateCaseStatus,
  type CaseDashboardOut,
  type DecisionListItemOut,
  type DocumentOut,
  type TaskOut,
  type VehicleOut,
} from "../lib/api";

type AttachSection = "documents" | "tasks" | "decisions" | "vehicles";

export default function CaseDetail() {
  const { id } = useParams<{ id: string }>();
  const [caseData, setCaseData] = useState<CaseDashboardOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attaching, setAttaching] = useState<AttachSection | null>(null);
  const [selected, setSelected] = useState("");
  const [allDocuments, setAllDocuments] = useState<DocumentOut[]>([]);
  const [allTasks, setAllTasks] = useState<TaskOut[]>([]);
  const [allDecisions, setAllDecisions] = useState<DecisionListItemOut[]>([]);
  const [allVehicles, setAllVehicles] = useState<VehicleOut[]>([]);

  function refresh() {
    if (!id) return;
    setLoading(true);
    getCase(id)
      .then(setCaseData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load case"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
    listDocuments().then(setAllDocuments).catch(() => undefined);
    listTasks().then(setAllTasks).catch(() => undefined);
    listDecisions().then(setAllDecisions).catch(() => undefined);
    listVehicles().then(setAllVehicles).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function toggleStatus() {
    if (!caseData) return;
    try {
      await updateCaseStatus(caseData.id, caseData.status === "open" ? "closed" : "open");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update case");
    }
  }

  async function handleAttach() {
    if (!caseData || !selected) return;
    try {
      if (attaching === "documents") await attachDocumentToCase(selected, caseData.id);
      if (attaching === "tasks") await linkTaskToCase(caseData.id, selected);
      if (attaching === "decisions") await linkDecisionToCase(caseData.id, selected);
      if (attaching === "vehicles") await linkVehicleToCase(caseData.id, selected);
      setAttaching(null);
      setSelected("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to attach item");
    }
  }

  if (loading) return <p className="text-slate-500">Loading…</p>;
  if (error && !caseData) return <p className="text-sm text-red-600">{error}</p>;
  if (!caseData) return null;

  const linkedDocumentIds = new Set(caseData.documents.map((d) => d.id));
  const linkedTaskIds = new Set(caseData.tasks.map((t) => t.id));
  const linkedDecisionIds = new Set(caseData.decisions.map((d) => d.id));
  const linkedVehicleIds = new Set(caseData.vehicles.map((v) => v.id));

  const attachOptions: Record<AttachSection, { id: string; label: string }[]> = {
    documents: allDocuments.filter((d) => !linkedDocumentIds.has(d.id)).map((d) => ({ id: d.id, label: d.title })),
    tasks: allTasks.filter((t) => !linkedTaskIds.has(t.id)).map((t) => ({ id: t.id, label: t.title })),
    decisions: allDecisions.filter((d) => !linkedDecisionIds.has(d.id)).map((d) => ({ id: d.id, label: d.summary })),
    vehicles: allVehicles
      .filter((v) => !linkedVehicleIds.has(v.id))
      .map((v) => ({ id: v.id, label: v.kenteken ?? v.vin ?? v.id })),
  };

  function AttachControl({ section }: { section: AttachSection }) {
    if (attaching !== section) {
      return (
        <button
          onClick={() => {
            setAttaching(section);
            setSelected("");
          }}
          className="text-xs text-slate-500 hover:text-slate-900"
        >
          + Attach
        </button>
      );
    }
    const options = attachOptions[section];
    return (
      <div className="flex items-center gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1 text-xs"
        >
          <option value="">Select…</option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
        <button onClick={handleAttach} disabled={!selected} className="text-xs text-slate-900 disabled:opacity-50">
          Attach
        </button>
        <button onClick={() => setAttaching(null)} className="text-xs text-slate-500 hover:text-slate-900">
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{caseData.name}</h1>
          {caseData.description && <p className="mt-1 text-sm text-slate-500">{caseData.description}</p>}
        </div>
        <button
          onClick={toggleStatus}
          className={`rounded px-3 py-1 text-xs ${
            caseData.status === "open" ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-600"
          }`}
        >
          {caseData.status}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium">Documents</span>
          <AttachControl section="documents" />
        </div>
        {caseData.documents.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.documents.map((d) => (
              <li key={d.id}>
                <Link to={`/documents/${d.id}`} className="text-sm hover:underline">
                  {d.title}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium">Tasks</span>
          <AttachControl section="tasks" />
        </div>
        {caseData.tasks.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.tasks.map((t) => (
              <li key={t.id} className="text-sm">
                {t.title} <span className="text-xs text-slate-400">({t.status})</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium">Decisions</span>
          <AttachControl section="decisions" />
        </div>
        {caseData.decisions.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.decisions.map((d) => (
              <li key={d.id} className="text-sm">
                {d.summary}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium">Vehicles</span>
          <AttachControl section="vehicles" />
        </div>
        {caseData.vehicles.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.vehicles.map((v) => (
              <li key={v.id} className="text-sm">
                {v.kenteken} {v.merk && <span className="text-xs text-slate-400">({v.merk} {v.handelsbenaming})</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
