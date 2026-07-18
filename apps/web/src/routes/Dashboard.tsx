import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import {
  listDocuments,
  listTasks,
  listCases,
  listEntities,
  getAdminHealth,
  type DocumentOut,
  type TaskOut,
  type CaseOut,
  type EntityOut,
  type ServiceHealthOut,
} from "../lib/api";
import { useDateFormat } from "../hooks/useDateFormat";
import { taskUrgency } from "../lib/taskUrgency";
import Card from "../components/Card";
import { DashboardWidgetCard } from "../components/DashboardWidgetCard";
import { Badge } from "../components/ui/Badge";

const QUICK_ACTIONS: { to: string; titleKey: string; descKey: string }[] = [
  { to: "/chat", titleKey: "dashboard.quickActionChat", descKey: "dashboard.quickActionChatDesc" },
  { to: "/legal", titleKey: "dashboard.quickActionLegal", descKey: "dashboard.quickActionLegalDesc" },
  { to: "/assistant", titleKey: "dashboard.quickActionAssistant", descKey: "dashboard.quickActionAssistantDesc" },
  { to: "/tasks", titleKey: "dashboard.quickActionTasks", descKey: "dashboard.quickActionTasksDesc" },
];

export function getGreetingKey(hour: number): "dashboard.greetingMorning" | "dashboard.greetingAfternoon" | "dashboard.greetingEvening" {
  if (hour < 12) return "dashboard.greetingMorning";
  if (hour < 18) return "dashboard.greetingAfternoon";
  return "dashboard.greetingEvening";
}

export default function Dashboard() {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
  const { user } = useAuth();

  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [pendingEntities, setPendingEntities] = useState<EntityOut[]>([]);
  const [pendingLoading, setPendingLoading] = useState(true);
  const [cases, setCases] = useState<CaseOut[]>([]);
  const [casesLoading, setCasesLoading] = useState(true);
  const [health, setHealth] = useState<ServiceHealthOut[]>([]);
  const [healthLoading, setHealthLoading] = useState(true);

  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch(() => {
        // Widgets degrade to their empty state on failure -- not core navigation.
      })
      .finally(() => setDocumentsLoading(false));
  }, []);

  useEffect(() => {
    listTasks("open")
      .then(setTasks)
      .catch(() => {})
      .finally(() => setTasksLoading(false));
  }, []);

  useEffect(() => {
    listEntities(undefined, undefined, "pending_review")
      .then(setPendingEntities)
      .catch(() => {})
      .finally(() => setPendingLoading(false));
  }, []);

  useEffect(() => {
    listCases()
      .then(setCases)
      .catch(() => {})
      .finally(() => setCasesLoading(false));
  }, []);

  useEffect(() => {
    if (user?.role !== "admin") {
      setHealthLoading(false);
      return;
    }
    getAdminHealth()
      .then(setHealth)
      .catch(() => {})
      .finally(() => setHealthLoading(false));
  }, [user?.role]);

  const recentDocuments = [...documents].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  const recentTasks = tasks.slice(0, 5);
  const recentCases = [...cases].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  const now = new Date();

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-ink">
        {t(getGreetingKey(now.getHours()), { name: user?.display_name ?? "" })}
      </h1>

      <Card>
        <h2 className="mb-3 text-sm font-semibold text-ink">{t("dashboard.quickActionsTitle")}</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {QUICK_ACTIONS.map((action) => (
            <Link
              key={action.to}
              to={action.to}
              className="flex flex-col gap-1 rounded-xl border border-edge px-3 py-2.5 transition-colors duration-fast hover:border-accent hover:bg-hover"
            >
              <span className="text-sm font-medium text-ink">{t(action.titleKey)}</span>
              <span className="text-xs text-ink-2">{t(action.descKey)}</span>
            </Link>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <DashboardWidgetCard
          title={t("dashboard.recentDocumentsTitle")}
          loading={documentsLoading}
          isEmpty={recentDocuments.length === 0}
          emptyMessage={t("dashboard.recentDocumentsEmpty")}
          actions={
            <Link to="/documents" className="text-xs text-accent hover:underline">
              {t("dashboard.viewAll")}
            </Link>
          }
        >
          <ul className="flex flex-col gap-2">
            {recentDocuments.map((doc) => (
              <li key={doc.id}>
                <Link to={`/documents/${doc.id}`} className="text-sm text-ink hover:text-accent">
                  {doc.title}
                </Link>
              </li>
            ))}
          </ul>
        </DashboardWidgetCard>

        <DashboardWidgetCard
          title={t("dashboard.myTasksTitle")}
          loading={tasksLoading}
          isEmpty={recentTasks.length === 0}
          emptyMessage={t("dashboard.myTasksEmpty")}
          actions={
            <Link to="/tasks" className="text-xs text-accent hover:underline">
              {t("dashboard.viewAll")}
            </Link>
          }
        >
          <ul className="flex flex-col gap-2">
            {recentTasks.map((task) => (
              <li key={task.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="text-ink">{task.title}</span>
                {task.due_date && (
                  <Badge variant={taskUrgency(task.due_date).variant}>
                    {taskUrgency(task.due_date).variant === "danger"
                      ? t("tasks.dueOverdue", { count: taskUrgency(task.due_date).overdueDays })
                      : taskUrgency(task.due_date).variant === "warning"
                        ? t("tasks.dueToday")
                        : t("tasks.due", { date: formatDate(task.due_date) })}
                  </Badge>
                )}
              </li>
            ))}
          </ul>
        </DashboardWidgetCard>

        <DashboardWidgetCard
          title={t("dashboard.pendingReviewsTitle")}
          loading={pendingLoading}
          isEmpty={pendingEntities.length === 0}
          emptyMessage={t("dashboard.pendingReviewsEmpty")}
        >
          <Link to="/entities/review" className="text-sm font-medium text-accent hover:underline">
            {t("dashboard.pendingReviewsCount", { count: pendingEntities.length })}
          </Link>
        </DashboardWidgetCard>

        <DashboardWidgetCard
          title={t("dashboard.recentCasesTitle")}
          loading={casesLoading}
          isEmpty={recentCases.length === 0}
          emptyMessage={t("dashboard.recentCasesEmpty")}
          actions={
            <Link to="/cases" className="text-xs text-accent hover:underline">
              {t("dashboard.viewAll")}
            </Link>
          }
        >
          <ul className="flex flex-col gap-2">
            {recentCases.map((c) => (
              <li key={c.id}>
                <Link to={`/cases/${c.id}`} className="text-sm text-ink hover:text-accent">
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        </DashboardWidgetCard>

        {user?.role === "admin" && (
          <DashboardWidgetCard
            title={t("dashboard.systemStatusTitle")}
            loading={healthLoading}
            isEmpty={health.length === 0}
            emptyMessage={t("dashboard.systemStatusEmpty")}
          >
            <ul className="flex flex-col gap-2">
              {health.map((service) => (
                <li key={service.name} className="flex items-center justify-between text-sm">
                  <span className="text-ink">{service.name}</span>
                  <Badge variant={service.status === "up" ? "success" : "danger"}>{service.status}</Badge>
                </li>
              ))}
            </ul>
          </DashboardWidgetCard>
        )}
      </div>
    </div>
  );
}
