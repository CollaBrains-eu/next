import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Card from "../components/Card";
import { Alert } from "../components/ui/Alert";
import { Breadcrumbs } from "../components/ui/Breadcrumbs";
import { Button } from "../components/ui/Button";
import { Combobox } from "../components/ui/Combobox";
import { SkeletonLines } from "../components/ui/Skeleton";
import { StatusPipeline } from "../components/ui/StatusPipeline";
import { Tooltip } from "../components/ui/Tooltip";
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
  const { t } = useTranslation();
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
      .catch((err) => setError(err instanceof ApiError ? err.message : t("caseDetail.loadError")))
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
      setError(err instanceof ApiError ? err.message : t("caseDetail.updateError"));
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
      setError(err instanceof ApiError ? err.message : t("caseDetail.attachError"));
    }
  }

  if (loading) return <SkeletonLines className="max-w-md" />;
  if (error && !caseData) return <Alert variant="danger" title={t("caseDetail.loadError")}>{error}</Alert>;
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
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setAttaching(section);
            setSelected("");
          }}
        >
          {t("caseDetail.attachAction")}
        </Button>
      );
    }
    const options = attachOptions[section];
    const selectedOption = options.find((o) => o.id === selected);
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Combobox
          multiple={false}
          options={options}
          selected={selectedOption ? [selectedOption] : []}
          onChange={(next) => setSelected(next[0]?.id ?? "")}
          placeholder={t("caseDetail.selectPlaceholder")}
        />
        <Button size="sm" onClick={handleAttach} disabled={!selected}>
          {t("caseDetail.attachConfirm")}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setAttaching(null)}>
          {t("common.cancel")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: t("nav.cases"), to: "/cases" }, { label: caseData.name }]} />

      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold text-ink">{caseData.name}</h1>
          {caseData.description && <p className="mt-1 text-sm text-ink-2">{caseData.description}</p>}
        </div>
        <Tooltip label="Toggle case status">
          <button onClick={toggleStatus} className="shrink-0 rounded-full" aria-label="Toggle case status">
            <StatusPipeline
              stages={[
                { key: "open", label: "open" },
                { key: "closed", label: "closed" },
              ]}
              currentKey={caseData.status}
            />
          </button>
        </Tooltip>
      </div>

      {error && <Alert variant="danger" dismissible onDismiss={() => setError(null)}>{error}</Alert>}

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-ink">{t("nav.documents")}</span>
          <AttachControl section="documents" />
        </div>
        {caseData.documents.length === 0 ? (
          <p className="text-sm text-ink-3">{t("caseDetail.nothingLinked")}</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.documents.map((d) => (
              <li key={d.id}>
                <Link to={`/documents/${d.id}`} className="text-sm text-ink hover:text-accent hover:underline">
                  {d.title}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-ink">{t("nav.tasks")}</span>
          <AttachControl section="tasks" />
        </div>
        {caseData.tasks.length === 0 ? (
          <p className="text-sm text-ink-3">{t("caseDetail.nothingLinked")}</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.tasks.map((t) => (
              <li key={t.id} className="text-sm text-ink">
                {t.title} <span className="text-xs text-ink-3">({t.status})</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-ink">{t("caseDetail.decisions")}</span>
          <AttachControl section="decisions" />
        </div>
        {caseData.decisions.length === 0 ? (
          <p className="text-sm text-ink-3">{t("caseDetail.nothingLinked")}</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.decisions.map((d) => (
              <li key={d.id} className="text-sm text-ink">
                {d.summary}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-ink">{t("nav.vehicles")}</span>
          <AttachControl section="vehicles" />
        </div>
        {caseData.vehicles.length === 0 ? (
          <p className="text-sm text-ink-3">{t("caseDetail.nothingLinked")}</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.vehicles.map((v) => (
              <li key={v.id} className="text-sm text-ink">
                {v.kenteken} {v.merk && <span className="text-xs text-ink-3">({v.merk} {v.handelsbenaming})</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
