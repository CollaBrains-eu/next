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
import { useDateFormat } from "../hooks/useDateFormat";
import {
  ApiError,
  attachDocumentToCase,
  getCase,
  inviteCaseMember,
  linkDecisionToCase,
  linkTaskToCase,
  linkVehicleToCase,
  listCaseMembers,
  listDecisions,
  listDocuments,
  listTasks,
  listVehicles,
  lookupUserByPhone,
  removeCaseMember,
  updateCaseStatus,
  type CaseDashboardOut,
  type CaseMemberOut,
  type DecisionListItemOut,
  type DocumentOut,
  type TaskOut,
  type VehicleOut,
} from "../lib/api";

type AttachSection = "documents" | "tasks" | "decisions" | "vehicles";

export default function CaseDetail() {
  const { t } = useTranslation();
  const { formatDateTime } = useDateFormat();
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
  const [members, setMembers] = useState<CaseMemberOut[]>([]);
  const [invitePhone, setInvitePhone] = useState("");
  const [inviteLookup, setInviteLookup] = useState<{ id: string; username: string; display_name: string } | null | "not-found">(null);
  const [inviteRole, setInviteRole] = useState<"worker" | "member">("member");
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  function refresh() {
    if (!id) return;
    setLoading(true);
    getCase(id)
      .then(setCaseData)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("caseDetail.loadError")))
      .finally(() => setLoading(false));
  }

  function refreshMembers() {
    if (!id) return;
    listCaseMembers(id).then(setMembers).catch(() => undefined);
  }

  useEffect(() => {
    refresh();
    refreshMembers();
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

  async function handleLookupPhone() {
    if (!invitePhone.trim()) return;
    setInviteError(null);
    setInviteLoading(true);
    try {
      const found = await lookupUserByPhone(invitePhone.trim());
      setInviteLookup(found ?? "not-found");
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : t("caseDetail.lookupError"));
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleInvite() {
    if (!caseData || !inviteLookup || inviteLookup === "not-found") return;
    setInviteLoading(true);
    setInviteError(null);
    try {
      await inviteCaseMember(caseData.id, inviteLookup.id, inviteRole);
      setInvitePhone("");
      setInviteLookup(null);
      setInviteRole("member");
      refreshMembers();
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : t("caseDetail.inviteError"));
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleRemoveMember(userId: string) {
    if (!caseData) return;
    try {
      await removeCaseMember(caseData.id, userId);
      refreshMembers();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("caseDetail.removeMemberError"));
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
          <p className="mt-1 text-xs text-ink-3">{t("caseDetail.ownedBy", { name: caseData.owner_display_name })}</p>
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
          <span className="text-xs font-bold uppercase tracking-wide text-ink-2">{t("nav.documents")}</span>
          <AttachControl section="documents" />
        </div>
        {caseData.documents.length === 0 ? (
          <p className="text-sm text-ink-3">{t("caseDetail.nothingLinked")}</p>
        ) : (
          <div className="flex flex-col divide-y divide-edge overflow-hidden rounded-xl border border-edge">
            {caseData.documents.map((d) => (
              <Link
                key={d.id}
                to={`/documents/${d.id}`}
                className="truncate px-3 py-2 text-sm text-ink transition-colors duration-fast hover:bg-hover hover:text-accent"
                title={d.title}
              >
                {d.title}
              </Link>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wide text-ink-2">{t("nav.tasks")}</span>
          <AttachControl section="tasks" />
        </div>
        {caseData.tasks.length === 0 ? (
          <p className="text-sm text-ink-3">{t("caseDetail.nothingLinked")}</p>
        ) : (
          <div className="flex flex-col divide-y divide-edge overflow-hidden rounded-xl border border-edge">
            {caseData.tasks.map((task) => (
              <div key={task.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm text-ink">
                <span className="truncate">{task.title}</span>
                <span className="shrink-0 text-xs text-ink-3">{task.status}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wide text-ink-2">{t("caseDetail.decisions")}</span>
          <AttachControl section="decisions" />
        </div>
        {caseData.decisions.length === 0 ? (
          <p className="text-sm text-ink-3">{t("caseDetail.nothingLinked")}</p>
        ) : (
          <div className="flex flex-col divide-y divide-edge overflow-hidden rounded-xl border border-edge">
            {caseData.decisions.map((d) => (
              <div key={d.id} className="px-3 py-2 text-sm text-ink">
                {d.summary}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wide text-ink-2">{t("nav.vehicles")}</span>
          <AttachControl section="vehicles" />
        </div>
        {caseData.vehicles.length === 0 ? (
          <p className="text-sm text-ink-3">{t("caseDetail.nothingLinked")}</p>
        ) : (
          <div className="flex flex-col divide-y divide-edge overflow-hidden rounded-xl border border-edge">
            {caseData.vehicles.map((v) => (
              <div key={v.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm text-ink">
                <span className="truncate font-mono">{v.kenteken}</span>
                {v.merk && (
                  <span className="shrink-0 text-xs text-ink-3">
                    {v.merk} {v.handelsbenaming}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wide text-ink-2">{t("nav.calendar")}</span>
        </div>
        {caseData.appointments.length === 0 ? (
          <p className="text-sm text-ink-3">{t("caseDetail.nothingLinked")}</p>
        ) : (
          <div className="flex flex-col divide-y divide-edge overflow-hidden rounded-xl border border-edge">
            {caseData.appointments.map((a) => (
              <div key={a.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm text-ink">
                <span className="truncate">{a.title}</span>
                <span className="shrink-0 text-xs text-ink-3">{formatDateTime(a.starts_at)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wide text-ink-2">{t("caseDetail.members")}</span>
        </div>

        {caseData.is_owner && (
          <div className="mb-3 flex flex-col gap-2 rounded-xl border border-edge p-3">
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={invitePhone}
                onChange={(e) => {
                  setInvitePhone(e.target.value);
                  setInviteLookup(null);
                }}
                placeholder={t("caseDetail.invitePhonePlaceholder")}
                className="flex-1 rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
              />
              <Button size="sm" variant="secondary" onClick={handleLookupPhone} disabled={inviteLoading || !invitePhone.trim()}>
                {t("caseDetail.lookupAction")}
              </Button>
            </div>
            {inviteLookup === "not-found" && (
              <p className="text-xs text-danger">{t("caseDetail.userNotFound")}</p>
            )}
            {inviteLookup && inviteLookup !== "not-found" && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-ink">{inviteLookup.display_name}</span>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as "worker" | "member")}
                  className="rounded-lg border border-edge bg-surface px-2 py-1 text-xs text-ink outline-none focus:border-accent"
                >
                  <option value="member">{t("caseDetail.roleMember")}</option>
                  <option value="worker">{t("caseDetail.roleWorker")}</option>
                </select>
                <Button size="sm" onClick={handleInvite} disabled={inviteLoading}>
                  {t("caseDetail.inviteAction")}
                </Button>
              </div>
            )}
            {inviteError && <p className="text-xs text-danger">{inviteError}</p>}
          </div>
        )}

        {members.filter((m) => m.status === "accepted").length === 0 ? (
          <p className="text-sm text-ink-3">{t("caseDetail.noMembers")}</p>
        ) : (
          <div className="flex flex-col divide-y divide-edge overflow-hidden rounded-xl border border-edge">
            {members
              .filter((m) => m.status === "accepted")
              .map((m) => (
                <div key={m.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm text-ink">
                  <span className="truncate">{m.user_display_name}</span>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-xs text-ink-3">{m.role}</span>
                    {caseData.is_owner && (
                      <Button size="sm" variant="ghost" onClick={() => handleRemoveMember(m.user_id)}>
                        {t("common.remove")}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
          </div>
        )}

        {caseData.is_owner && members.filter((m) => m.status === "pending").length > 0 && (
          <div className="mt-3">
            <span className="text-xs font-semibold text-ink-2">{t("caseDetail.pendingInvites")}</span>
            <div className="mt-1 flex flex-col divide-y divide-edge overflow-hidden rounded-xl border border-edge">
              {members
                .filter((m) => m.status === "pending")
                .map((m) => (
                  <div key={m.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm text-ink">
                    <span className="truncate">{m.user_display_name}</span>
                    <Button size="sm" variant="ghost" onClick={() => handleRemoveMember(m.user_id)}>
                      {t("caseDetail.revokeInvite")}
                    </Button>
                  </div>
                ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
