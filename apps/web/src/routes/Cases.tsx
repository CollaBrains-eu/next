import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { SkeletonLines } from "../components/ui/Skeleton";
import {
  acceptCaseInvitation,
  ApiError,
  createCase,
  declineCaseInvitation,
  downloadCasesCsv,
  listCases,
  listMyCaseInvitations,
  type CaseMemberOut,
  type CaseOut,
} from "../lib/api";
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
  const [exporting, setExporting] = useState(false);
  const [invitations, setInvitations] = useState<CaseMemberOut[]>([]);

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
  }, []);

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

  const newCaseButton = !creating && (
    <Button onClick={() => setCreating(true)}>{t("cases.newCase")}</Button>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">{t("cases.title")}</h1>
        <div className="flex items-center gap-2">
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
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {cases.map((c, index) => (
            <Link key={c.id} to={`/cases/${c.id}`} className="card-tilt animate-cardIn rounded-2xl opacity-0" style={{ animationDelay: `${Math.min(index, 8) * 90}ms` }}>
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
