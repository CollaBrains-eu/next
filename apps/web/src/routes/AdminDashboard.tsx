import { useEffect, useState } from "react";
import Card from "../components/Card";
import { Button } from "../components/ui/Button";
import {
  ApiError,
  analyzeBugReport,
  type AdminStatsOut,
  type AiUsageRowOut,
  type BugReportOut,
  type ServiceHealthOut,
  getAdminAiUsage,
  getAdminHealth,
  getAdminStats,
  listBugReports,
} from "../lib/api";

type Tab = "overview" | "ai-usage" | "health" | "bugs";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "ai-usage", label: "AI usage" },
  { id: "health", label: "Health" },
  { id: "bugs", label: "Bug reports" },
];

export default function AdminDashboard() {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">Admin</h1>

      <div className="flex gap-2 border-b border-edge">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-2 text-sm font-medium ${
              tab === t.id ? "border-b-2 border-accent text-accent" : "text-ink-3 hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab />}
      {tab === "ai-usage" && <AiUsageTab />}
      {tab === "health" && <HealthTab />}
      {tab === "bugs" && <BugsTab />}
    </div>
  );
}

function OverviewTab() {
  const [stats, setStats] = useState<AdminStatsOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminStats()
      .then(setStats)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load stats"));
  }, []);

  if (error) return <p className="text-danger">{error}</p>;
  if (!stats) return <p className="text-ink-3">Loading…</p>;

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Card>
        <p className="text-xs text-ink-3">Users</p>
        <p className="text-2xl font-semibold text-ink">{stats.total_users}</p>
      </Card>
      <Card>
        <p className="text-xs text-ink-3">Documents</p>
        <p className="text-2xl font-semibold text-ink">{stats.total_documents}</p>
      </Card>
      <Card>
        <p className="text-xs text-ink-3">AI calls (24h)</p>
        <p className="text-2xl font-semibold text-ink">{stats.ai_calls_last_24h}</p>
      </Card>
      <Card className="col-span-2 sm:col-span-1">
        <p className="text-xs text-ink-3">Documents by status</p>
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
  const [rows, setRows] = useState<AiUsageRowOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminAiUsage("model")
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load AI usage"));
  }, []);

  if (error) return <p className="text-danger">{error}</p>;
  if (!rows) return <p className="text-ink-3">Loading…</p>;

  return (
    <Card>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-ink-3">
            <th className="pb-2">Model</th>
            <th className="pb-2">Calls</th>
            <th className="pb-2">Prompt tokens</th>
            <th className="pb-2">Completion tokens</th>
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
  const [rows, setRows] = useState<ServiceHealthOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminHealth()
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load health"));
  }, []);

  if (error) return <p className="text-danger">{error}</p>;
  if (!rows) return <p className="text-ink-3">Loading…</p>;

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
  const [reports, setReports] = useState<BugReportOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);

  function load() {
    listBugReports()
      .then(setReports)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load bug reports"));
  }

  useEffect(load, []);

  async function handleAnalyze(id: string) {
    setAnalyzingId(id);
    try {
      await analyzeBugReport(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to analyze bug report");
    } finally {
      setAnalyzingId(null);
    }
  }

  if (error) return <p className="text-danger">{error}</p>;
  if (!reports) return <p className="text-ink-3">Loading…</p>;
  if (reports.length === 0) return <p className="text-ink-3">No bug reports.</p>;

  return (
    <div className="flex flex-col gap-3">
      {reports.map((report) => (
        <Card key={report.id} className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-ink-3">{new Date(report.created_at).toLocaleString()}</span>
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
              {analyzingId === report.id ? "Analyzing…" : "Analyze with AI"}
            </Button>
          )}
        </Card>
      ))}
    </div>
  );
}
