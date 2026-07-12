import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import Card from "../components/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { TextField } from "../components/ui/form";
import { DataTable, type Column } from "../components/ui/DataTable";
import { useDateFormat } from "../hooks/useDateFormat";
import {
  ApiError,
  analyzeBugReport,
  createAdminUser,
  listAdminUsers,
  type AdminStatsOut,
  type AdminUserCreatedOut,
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
  if (!stats) return <p className="text-ink-3">{t("common.loading")}</p>;

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
  if (!rows) return <p className="text-ink-3">{t("common.loading")}</p>;

  return (
    <Card>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-ink-3">
            <th className="pb-2">{t("admin.columnModel")}</th>
            <th className="pb-2">{t("admin.columnCalls")}</th>
            <th className="pb-2">{t("admin.columnPromptTokens")}</th>
            <th className="pb-2">{t("admin.columnCompletionTokens")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-t border-edge text-ink">
              <td className="py-2">{row.key}</td>
              <td className="py-2">{row.call_count}</td>
              <td className="py-2">{row.total_prompt_tokens}</td>
              <td className="py-2">{row.total_completion_tokens}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
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
  if (!rows) return <p className="text-ink-3">{t("common.loading")}</p>;

  return (
    <div className="flex flex-col gap-2">
      {rows.map((row) => (
        <Card key={row.name} className="flex items-center justify-between">
          <span className="text-ink">{row.name}</span>
          <span className={row.status === "up" ? "text-success" : "text-danger"}>
            {row.status}
            {row.detail ? ` — ${row.detail}` : ""}
          </span>
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
  if (!reports) return <p className="text-ink-3">{t("common.loading")}</p>;
  if (reports.length === 0) return <p className="text-ink-3">{t("admin.noBugReports")}</p>;

  return (
    <div className="flex flex-col gap-3">
      {reports.map((report) => (
        <Card key={report.id} className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-ink-3">{formatDateTime(report.created_at)}</span>
            <span className="text-xs uppercase text-ink-3">{report.status}</span>
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
  const [created, setCreated] = useState<AdminUserCreatedOut | null>(null);

  const [users, setUsers] = useState<AdminUserOut[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [usersError, setUsersError] = useState<string | null>(null);
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
      setCreated(result);
      loadUsers(0);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("admin.createUserError"));
    } finally {
      setSubmitting(false);
    }
  }

  const columns: Column<AdminUserOut>[] = [
    { key: "username", header: t("admin.usernameLabel"), render: (row) => row.username },
    { key: "display_name", header: t("admin.displayNameLabel"), render: (row) => row.display_name },
    { key: "email", header: t("admin.emailLabel"), render: (row) => row.email ?? "" },
    {
      key: "role",
      header: t("admin.roleColumn"),
      render: (row) => <Badge variant={row.role === "admin" ? "warning" : "default"}>{row.role}</Badge>,
    },
    { key: "phone_number", header: t("admin.phoneColumn"), render: (row) => row.phone_number ?? "" },
    {
      key: "created_at",
      header: t("admin.createdAtColumn"),
      render: (row) => formatDate(row.created_at),
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

      {created && (
        <Card className="flex flex-col gap-2 border-accent">
          <p className="text-sm font-medium text-ink">
            {t("admin.userCreated", { username: created.username })}
          </p>
          <p className="text-xs text-ink-3">{t("admin.tempPasswordHint")}</p>
          <code className="rounded-lg bg-accent-soft px-3 py-2 text-sm text-ink" data-testid="temp-password">
            {created.temporary_password}
          </code>
          <div>
            <Button size="sm" variant="ghost" onClick={() => setCreated(null)}>
              {t("admin.dismiss")}
            </Button>
          </div>
        </Card>
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={t("admin.addUserModalTitle")}>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {error && <p className="text-sm text-danger">{error}</p>}
          <label className="flex flex-col gap-1 text-sm text-ink-2">
            {t("admin.usernameLabel")}
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-ink-2">
            {t("admin.displayNameLabel")}
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-ink-2">
            {t("admin.emailLabel")}
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </label>
          <TextField
            label={t("admin.phoneColumn")}
            value={phoneNumber}
            onChange={setPhoneNumber}
            placeholder="+491511234567"
          />
          <label className="flex items-center gap-2 text-sm text-ink-2">
            <input type="checkbox" checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />
            {t("admin.adminRoleLabel")}
          </label>
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

      {usersError ? (
        <p className="text-danger">{usersError}</p>
      ) : usersLoading ? (
        <p className="text-ink-3">{t("common.loading")}</p>
      ) : (
        <>
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
