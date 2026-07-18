import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import Card from "../components/Card";
import { TempPasswordCard } from "../components/TempPasswordCard";
import EmptyState from "../components/EmptyState";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { Checkbox, TextField } from "../components/ui/form";
import { DataTable, type Column } from "../components/ui/DataTable";
import { Dropdown, type DropdownOption } from "../components/ui/Dropdown";
import { useDateFormat } from "../hooks/useDateFormat";
import { SkeletonLines } from "../components/ui/Skeleton";
import {
  ApiError,
  analyzeBugReport,
  createAdminUser,
  listAdminUsers,
  setUserRole,
  setUserPhone,
  resetUserPassword,
  deactivateUser,
  type AdminStatsOut,
  type AdminUserOut,
  type AiUsageRowOut,
  type BugReportOut,
  type ServiceHealthOut,
  getAdminAiUsage,
  getAdminHealth,
  getAdminStats,
  listBugReports,
} from "../lib/api";

const USERS_PAGE_SIZE = 50;

type Tab = "overview" | "ai-usage" | "health" | "bugs" | "users";

export default function AdminDashboard() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("overview");

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: t("admin.tabOverview") },
    { id: "ai-usage", label: t("admin.tabAiUsage") },
    { id: "health", label: t("admin.tabHealth") },
    { id: "bugs", label: t("admin.tabBugs") },
    { id: "users", label: t("admin.tabUsers") },
  ];

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">{t("admin.title")}</h1>

      <div className="flex gap-2 overflow-x-auto border-b border-edge">
        {tabs.map((tabOption) => (
          <button
            key={tabOption.id}
            onClick={() => setTab(tabOption.id)}
            className={`shrink-0 px-3 py-2 text-sm font-medium ${
              tab === tabOption.id ? "border-b-2 border-accent text-accent" : "text-ink-3 hover:text-ink"
            }`}
          >
            {tabOption.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab />}
      {tab === "ai-usage" && <AiUsageTab />}
      {tab === "health" && <HealthTab />}
      {tab === "bugs" && <BugsTab />}
      {tab === "users" && <UsersTab />}
    </div>
  );
}

function OverviewTab() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<AdminStatsOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminStats()
      .then(setStats)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("admin.statsLoadError")));
  }, [t]);

  if (error) return <p className="text-danger">{error}</p>;
  if (!stats) return <SkeletonLines className="max-w-md" />;

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Card>
        <p className="text-xs text-ink-3">{t("admin.statUsers")}</p>
        <p className="text-2xl font-semibold text-ink">{stats.total_users}</p>
      </Card>
      <Card>
        <p className="text-xs text-ink-3">{t("admin.statDocuments")}</p>
        <p className="text-2xl font-semibold text-ink">{stats.total_documents}</p>
      </Card>
      <Card>
        <p className="text-xs text-ink-3">{t("admin.statAiCalls24h")}</p>
        <p className="text-2xl font-semibold text-ink">{stats.ai_calls_last_24h}</p>
      </Card>
      <Card className="col-span-2 sm:col-span-1">
        <p className="text-xs text-ink-3">{t("admin.statDocumentsByStatus")}</p>
        <ul className="text-sm text-ink">
          {Object.entries(stats.documents_by_status).map(([status, count]) => (
            <li key={status}>
              {status}: {count}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function AiUsageTab() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<AiUsageRowOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminAiUsage("model")
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("admin.aiUsageLoadError")));
  }, [t]);

  if (error) return <p className="text-danger">{error}</p>;
  if (!rows) return <SkeletonLines />;

  const columns: Column<AiUsageRowOut>[] = [
    { key: "model", header: t("admin.columnModel"), render: (row) => row.key },
    { key: "calls", header: t("admin.columnCalls"), render: (row) => row.call_count },
    { key: "prompt", header: t("admin.columnPromptTokens"), render: (row) => row.total_prompt_tokens },
    { key: "completion", header: t("admin.columnCompletionTokens"), render: (row) => row.total_completion_tokens },
  ];

  return <DataTable columns={columns} rows={rows} rowKey={(row) => row.key} pageSize={Math.max(rows.length, 1)} />;
}

function HealthTab() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<ServiceHealthOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminHealth()
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("admin.healthLoadError")));
  }, [t]);

  if (error) return <p className="text-danger">{error}</p>;
  if (!rows) return <SkeletonLines />;

  return (
    <div className="flex flex-col gap-2">
      {rows.map((row) => (
        <Card key={row.name} className="flex items-center justify-between">
          <span className="text-ink">{row.name}</span>
          <div className="flex items-center gap-2">
            <Badge variant={row.status === "up" ? "success" : "danger"}>{row.status}</Badge>
            {row.detail && <span className="text-xs text-ink-3">{row.detail}</span>}
          </div>
        </Card>
      ))}
    </div>
  );
}

function BugsTab() {
  const { t } = useTranslation();
  const { formatDateTime } = useDateFormat();
  const [reports, setReports] = useState<BugReportOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);

  function load() {
    listBugReports()
      .then(setReports)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("admin.bugsLoadError")));
  }

  useEffect(load, []);

  async function handleAnalyze(id: string) {
    setAnalyzingId(id);
    try {
      await analyzeBugReport(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("admin.analyzeError"));
    } finally {
      setAnalyzingId(null);
    }
  }

  if (error) return <p className="text-danger">{error}</p>;
  if (!reports) return <SkeletonLines className="max-w-md" />;
  if (reports.length === 0) return <EmptyState message={t("admin.noBugReports")} />;

  return (
    <div className="flex flex-col gap-3">
      {reports.map((report) => (
        <Card key={report.id} className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-ink-3">{formatDateTime(report.created_at)}</span>
            <Badge variant={report.status === "closed" ? "success" : report.status === "analyzed" ? "default" : "warning"}>
              {report.status}
            </Badge>
          </div>
          <p className="text-sm text-ink">{report.description}</p>
          {report.ai_analysis ? (
            <p className="rounded-lg bg-accent-soft p-2 text-sm text-ink">{report.ai_analysis}</p>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleAnalyze(report.id)}
              disabled={analyzingId === report.id}
            >
              {analyzingId === report.id ? t("admin.analyzing") : t("admin.analyzeWithAi")}
            </Button>
          )}
        </Card>
      ))}
    </div>
  );
}

function UsersTab() {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
  const [formOpen, setFormOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tempPassword, setTempPassword] = useState<{ message: string; password: string } | null>(null);

  const [users, setUsers] = useState<AdminUserOut[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [phoneModalUser, setPhoneModalUser] = useState<AdminUserOut | null>(null);
  const [phoneInput, setPhoneInput] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [phoneSaving, setPhoneSaving] = useState(false);
  const [deactivateTarget, setDeactivateTarget] = useState<AdminUserOut | null>(null);
  const [deactivating, setDeactivating] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  async function loadUsers(offset: number) {
    try {
      const page = await listAdminUsers(USERS_PAGE_SIZE, offset);
      setUsers((prev) => (offset === 0 ? page : [...prev, ...page]));
      setHasMore(page.length === USERS_PAGE_SIZE);
    } catch (err) {
      setUsersError(err instanceof ApiError ? err.message : t("admin.usersLoadError"));
    } finally {
      setUsersLoading(false);
    }
  }

  useEffect(() => {
    loadUsers(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function resetForm() {
    setUsername("");
    setDisplayName("");
    setEmail("");
    setPhoneNumber("");
    setIsAdmin(false);
    setError(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await createAdminUser({
        username, display_name: displayName, email, is_admin: isAdmin,
        phone_number: phoneNumber.trim() || null,
      });
      setFormOpen(false);
      resetForm();
      setTempPassword({ message: t("admin.userCreated", { username: result.username }), password: result.temporary_password });
      loadUsers(0);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("admin.createUserError"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRoleChange(user: AdminUserOut, role: "member" | "admin") {
    setRowError(null);
    try {
      const updated = await setUserRole(user.id, role);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : t("admin.roleUpdateError"));
    }
  }

  async function handleSavePhone() {
    if (!phoneModalUser) return;
    setPhoneSaving(true);
    setPhoneError(null);
    try {
      const updated = await setUserPhone(phoneModalUser.id, phoneInput.trim() || null);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setPhoneModalUser(null);
    } catch (err) {
      setPhoneError(err instanceof ApiError ? err.message : t("admin.phoneUpdateError"));
    } finally {
      setPhoneSaving(false);
    }
  }

  async function handleResetPassword(user: AdminUserOut) {
    setRowError(null);
    try {
      const result = await resetUserPassword(user.id);
      setTempPassword({ message: t("admin.passwordReset", { username: result.username }), password: result.temporary_password });
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : t("admin.resetPasswordError"));
    }
  }

  async function handleDeactivate() {
    if (!deactivateTarget) return;
    setDeactivating(true);
    setRowError(null);
    try {
      await deactivateUser(deactivateTarget.id);
      setUsers((prev) => prev.map((u) => (u.id === deactivateTarget.id ? { ...u, is_active: false } : u)));
      setDeactivateTarget(null);
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : t("admin.deactivateError"));
    } finally {
      setDeactivating(false);
    }
  }

  const columns: Column<AdminUserOut>[] = [
    { key: "username", header: t("admin.usernameLabel"), render: (row) => row.username },
    { key: "display_name", header: t("admin.displayNameLabel"), render: (row) => row.display_name },
    { key: "email", header: t("admin.emailLabel"), render: (row) => row.email ?? "" },
    {
      key: "role",
      header: t("admin.roleColumn"),
      render: (row) => (
        <div className="flex items-center gap-1.5">
          <Badge variant={row.role === "admin" ? "warning" : "default"}>{row.role}</Badge>
          {!row.is_active && <Badge variant="danger">{t("admin.deactivatedBadge")}</Badge>}
        </div>
      ),
    },
    { key: "phone_number", header: t("admin.phoneColumn"), render: (row) => row.phone_number ?? "" },
    {
      key: "created_at",
      header: t("admin.createdAtColumn"),
      render: (row) => formatDate(row.created_at),
    },
    {
      key: "actions",
      header: "",
      render: (row) => {
        if (row.role === "service" || !row.is_active) return null;
        const options: DropdownOption[] = [
          {
            label: row.role === "admin" ? t("admin.makeMember") : t("admin.makeAdmin"),
            onSelect: () => handleRoleChange(row, row.role === "admin" ? "member" : "admin"),
          },
          {
            label: t("admin.setPhone"),
            onSelect: () => {
              setPhoneModalUser(row);
              setPhoneInput(row.phone_number ?? "");
              setPhoneError(null);
            },
          },
          {
            label: t("admin.resetPassword"),
            onSelect: () => handleResetPassword(row),
          },
          {
            label: t("admin.deactivate"),
            danger: true,
            onSelect: () => setDeactivateTarget(row),
          },
        ];
        return (
          <Dropdown
            trigger={
              <span className="rounded-lg px-2 py-1 text-xs text-ink-3 hover:bg-hover hover:text-ink">
                {t("admin.rowActions")}
              </span>
            }
            options={options}
          />
        );
      },
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Button
          size="sm"
          onClick={() => {
            resetForm();
            setFormOpen(true);
          }}
        >
          {t("admin.addUser")}
        </Button>
      </div>

      {tempPassword && (
        <TempPasswordCard
          message={tempPassword.message}
          password={tempPassword.password}
          onDismiss={() => setTempPassword(null)}
        />
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={t("admin.addUserModalTitle")}>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {error && <p className="text-sm text-danger">{error}</p>}
          <TextField
            label={t("admin.usernameLabel")}
            value={username}
            onChange={setUsername}
            required
          />
          <TextField
            label={t("admin.displayNameLabel")}
            value={displayName}
            onChange={setDisplayName}
            required
          />
          <TextField
            label={t("admin.emailLabel")}
            type="email"
            value={email}
            onChange={setEmail}
            required
          />
          <TextField
            label={t("admin.phoneColumn")}
            value={phoneNumber}
            onChange={setPhoneNumber}
            placeholder="+491511234567"
          />
          <Checkbox label={t("admin.adminRoleLabel")} checked={isAdmin} onChange={setIsAdmin} />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => setFormOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? t("admin.creating") : t("admin.createUser")}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={phoneModalUser !== null}
        onClose={() => setPhoneModalUser(null)}
        title={t("admin.phoneModalTitle")}
      >
        <div className="flex flex-col gap-3">
          {phoneError && <p className="text-sm text-danger">{phoneError}</p>}
          <TextField label={t("admin.phoneColumn")} value={phoneInput} onChange={setPhoneInput} placeholder="+491511234567" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => setPhoneModalUser(null)}>
              {t("common.cancel")}
            </Button>
            <Button type="button" size="sm" disabled={phoneSaving} onClick={handleSavePhone}>
              {t("admin.save")}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={deactivateTarget !== null}
        onClose={() => setDeactivateTarget(null)}
        title={t("admin.deactivateConfirmTitle")}
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink">
            {deactivateTarget && t("admin.deactivateConfirmBody", { displayName: deactivateTarget.display_name })}
          </p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => setDeactivateTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button type="button" variant="danger" size="sm" disabled={deactivating} onClick={handleDeactivate}>
              {t("admin.deactivate")}
            </Button>
          </div>
        </div>
      </Modal>

      {usersError ? (
        <p className="text-danger">{usersError}</p>
      ) : usersLoading ? (
        <SkeletonLines />
      ) : (
        <>
          {rowError && <p className="text-sm text-danger">{rowError}</p>}
          <DataTable columns={columns} rows={users} rowKey={(row) => row.id} pageSize={Math.max(users.length, 1)} />
          {hasMore && (
            <div>
              <Button size="sm" variant="secondary" onClick={() => loadUsers(users.length)}>
                {t("admin.loadMore")}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
