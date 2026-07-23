import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { BulkActionBar } from "../components/ui/BulkActionBar";
import { Column, DataTable } from "../components/ui/DataTable";
import { FilterChips } from "../components/ui/FilterChips";
import { SkeletonLines } from "../components/ui/Skeleton";
import { TextField } from "../components/ui/form";
import { useBulkSelection } from "../hooks/useBulkSelection";
import { ActivityTab } from "../components/ActivityTab";
import { CaseDetailContent } from "../components/CaseDetailContent";
import { DeleteConfirmButton } from "../components/DeleteConfirmButton";
import { Drawer } from "../components/ui/Drawer";
import { ShareButton } from "../components/ShareButton";
import {
  acceptCaseInvitation,
  ApiError,
  createCase,
  declineCaseInvitation,
  deleteCase,
  downloadCasesCsv,
  getCase,
  listCases,
  listMyCaseInvitations,
  updateCaseStatus,
  type CaseDashboardOut,
  type CaseMemberOut,
  type CaseOut,
} from "../lib/api";
import { useDateFormat } from "../hooks/useDateFormat";
import { useToast } from "../lib/toast";

type ViewMode = "cards" | "table";

export default function Cases() {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [selectedCase, setSelectedCase] = useState<CaseDashboardOut | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [cases, setCases] = useState<CaseOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [nameQuery, setNameQuery] = useState("");
  const [statusFilters, setStatusFilters] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>("cards");
  const { isSelected, toggle, clear, selectedCount, selectedKeys } = useBulkSelection<CaseOut>((c) => c.id);
  const [invitations, setInvitations] = useState<CaseMemberOut[]>([]);

  const STATUS_FILTER_OPTIONS = [
    { id: "open", label: t("cases.filterOpen") },
    { id: "closed", label: t("cases.filterClosed") },
  ];

  function refresh() {
    setLoading(true);
    listCases()
      .then(setCases)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("cases.loadError")))
      .finally(() => setLoading(false));
  }

  function refreshInvitations() {
    listMyCaseInvitations().then(setInvitations).catch(() => undefined);
  }

  useEffect(() => {
    refresh();
    refreshInvitations();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  }, []);

  function loadSelected() {
    if (!id) return;
    getCase(id).then(setSelectedCase).catch(() => setSelectedCase(null));
  }

  useEffect(() => {
    setSelectedCase(null);
    loadSelected();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleDrawerDelete() {
    if (!id || !selectedCase) return;
    setDeleting(true);
    try {
      await deleteCase(id);
      showToast(t("caseDetail.deletedToast", { name: selectedCase.name }));
      navigate("/cases");
      refresh();
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : t("caseDetail.deleteError"));
    } finally {
      setDeleting(false);
    }
  }

  async function handleAcceptInvitation(invitation: CaseMemberOut) {
    try {
      await acceptCaseInvitation(invitation.case_id, invitation.user_id);
      setInvitations((prev) => prev.filter((i) => i.id !== invitation.id));
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("cases.invitationError"));
    }
  }

  async function handleDeclineInvitation(invitation: CaseMemberOut) {
    try {
      await declineCaseInvitation(invitation.case_id, invitation.user_id);
      setInvitations((prev) => prev.filter((i) => i.id !== invitation.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("cases.invitationError"));
    }
  }

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

  async function handleExportCsv() {
    setExporting(true);
    try {
      await downloadCasesCsv();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("cases.exportError"));
    } finally {
      setExporting(false);
    }
  }

  async function handleBulkSetStatus(targetStatus: "open" | "closed") {
    const ids = cases.filter((c) => selectedKeys.has(c.id) && c.status !== targetStatus).map((c) => c.id);
    if (ids.length === 0) {
      clear();
      return;
    }
    try {
      await Promise.all(ids.map((id) => updateCaseStatus(id, targetStatus)));
      clear();
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("cases.updateError"));
    }
  }

  const activeStatusFilters = useMemo(() => new Set(statusFilters), [statusFilters]);
  const filteredCases = useMemo(
    () =>
      cases.filter(
        (c) =>
          (activeStatusFilters.size === 0 || activeStatusFilters.has(c.status)) &&
          (nameQuery.trim() === "" ||
            c.name.toLowerCase().includes(nameQuery.trim().toLowerCase()) ||
            (c.description ?? "").toLowerCase().includes(nameQuery.trim().toLowerCase()))
      ),
    [cases, activeStatusFilters, nameQuery]
  );

  const columns: Column<CaseOut>[] = [
    {
      key: "select",
      header: "",
      render: (c) => (
        <input
          type="checkbox"
          checked={isSelected(c)}
          onChange={() => toggle(c)}
          onClick={(event) => event.stopPropagation()}
          className="h-4 w-4 accent-accent"
        />
      ),
    },
    {
      key: "name",
      header: t("cases.columnName"),
      sortable: true,
      sortValue: (c) => c.name.toLowerCase(),
      render: (c) => (
        <Link to={`/cases/${c.id}`} className="font-medium text-ink hover:text-accent">
          {c.name}
        </Link>
      ),
    },
    {
      key: "status",
      header: t("cases.columnStatus"),
      sortable: true,
      sortValue: (c) => c.status,
      render: (c) => <Badge variant={c.status === "open" ? "success" : "default"}>{c.status}</Badge>,
    },
    {
      key: "document_count",
      header: t("cases.columnDocuments"),
      sortable: true,
      sortValue: (c) => c.document_count,
      render: (c) => c.document_count,
    },
    {
      key: "member_count",
      header: t("cases.columnMembers"),
      sortable: true,
      sortValue: (c) => c.member_count,
      render: (c) => c.member_count,
    },
    {
      key: "created_at",
      header: t("cases.columnCreated"),
      sortable: true,
      sortValue: (c) => c.created_at,
      render: (c) => formatDate(c.created_at),
    },
  ];

  const newCaseButton = !creating && (
    <Button onClick={() => setCreating(true)}>{t("cases.newCase")}</Button>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">{t("cases.title")}</h1>
        <div className="flex items-center gap-2">
          {cases.length > 0 && (
            <div className="flex gap-1 border-r border-edge pr-2">
              {(["cards", "table"] as ViewMode[]).map((mode) => (
                <Button
                  key={mode}
                  size="sm"
                  variant={viewMode === mode ? "primary" : "ghost"}
                  onClick={() => setViewMode(mode)}
                >
                  {mode === "cards" ? t("cases.viewCards") : t("cases.viewTable")}
                </Button>
              ))}
            </div>
          )}
          {cases.length > 0 && (
            <Button variant="secondary" onClick={handleExportCsv} disabled={exporting}>
              {t("cases.exportCsv")}
            </Button>
          )}
          {cases.length > 0 && newCaseButton}
        </div>
      </div>

      {invitations.length > 0 && (
        <Card>
          <span className="text-xs font-bold uppercase tracking-wide text-ink-2">{t("cases.pendingInvitationsTitle")}</span>
          <div className="mt-2 flex flex-col divide-y divide-edge">
            {invitations.map((invitation) => (
              <div key={invitation.id} className="flex items-center justify-between gap-3 py-2 text-sm text-ink">
                <span className="truncate">{invitation.case_name}</span>
                <div className="flex shrink-0 gap-2">
                  <Button size="sm" onClick={() => handleAcceptInvitation(invitation)}>
                    {t("cases.acceptInvitation")}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => handleDeclineInvitation(invitation)}>
                    {t("cases.declineInvitation")}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

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
        <SkeletonLines />
      ) : cases.length === 0 && !creating ? (
        <EmptyState heading={t("cases.emptyMessage")} message={t("cases.emptyMessageSub")} action={newCaseButton} />
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-full max-w-xs">
              <TextField label={t("cases.searchLabel")} value={nameQuery} onChange={setNameQuery} placeholder={t("cases.searchPlaceholder")} />
            </div>
            <FilterChips
              label={t("cases.statusFilterLabel")}
              chips={STATUS_FILTER_OPTIONS.filter((opt) => statusFilters.includes(opt.id))}
              onRemove={(id) => setStatusFilters((prev) => prev.filter((s) => s !== id))}
              addOptions={STATUS_FILTER_OPTIONS.filter((opt) => !statusFilters.includes(opt.id))}
              onAdd={(opt) => setStatusFilters((prev) => [...prev, opt.id])}
            />
          </div>

          {viewMode === "table" ? (
            <DataTable columns={columns} rows={filteredCases} rowKey={(c) => c.id} />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {filteredCases.map((c, index) => (
                <Link
                  key={c.id}
                  to={`/cases/${c.id}`}
                  className="card-tilt animate-cardIn rounded-2xl opacity-0"
                  style={{ animationDelay: `${Math.min(index, 8) * 90}ms` }}
                >
                  <Card className="flex h-full flex-col gap-2 transition-colors duration-fast hover:border-accent">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-ink">{c.name}</span>
                      <Badge variant={c.status === "open" ? "success" : "default"}>{c.status}</Badge>
                    </div>
                    {c.description && <p className="text-sm text-ink-2">{c.description}</p>}
                    <span className="mt-auto text-xs text-ink-3">
                      {t("cases.cardMeta", { docs: c.document_count, members: c.member_count })} · {formatDate(c.created_at)}
                    </span>
                  </Card>
                </Link>
              ))}
            </div>
          )}

          <BulkActionBar
            count={selectedCount}
            onCancel={clear}
            actions={[
              { label: t("cases.bulkClose"), onClick: () => handleBulkSetStatus("closed") },
              { label: t("cases.bulkReopen"), onClick: () => handleBulkSetStatus("open") },
            ]}
          />
        </>
      )}

      <Drawer
        open={!!id}
        onClose={() => navigate("/cases")}
        title={selectedCase?.name ?? ""}
        tabs={[
          {
            id: "details",
            label: t("drawer.details"),
            content: selectedCase ? (
              <CaseDetailContent caseData={selectedCase} onChanged={loadSelected} />
            ) : (
              <SkeletonLines />
            ),
          },
          {
            id: "activity",
            label: t("drawer.activity"),
            content: id ? <ActivityTab entityType="case" entityId={id} /> : null,
          },
        ]}
        footer={
          id && (
            <>
              <ShareButton entityType="case" entityId={id} />
              <DeleteConfirmButton
                confirmTitle={t("caseDetail.deleteModalTitle", { name: selectedCase?.name ?? "" })}
                confirmBody={t("caseDetail.deleteModalBody")}
                confirmLabel={t("caseDetail.deleteConfirm")}
                onConfirm={handleDrawerDelete}
                deleting={deleting}
              />
            </>
          )
        }
      />
    </div>
  );
}
