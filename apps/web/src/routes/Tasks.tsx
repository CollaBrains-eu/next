import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  createTask,
  listTasks,
  moveTask,
  updateTaskStatus,
  type RecurrenceRule,
  type TaskOut,
  type TaskStatus,
} from "../lib/api";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { KanbanBoard } from "../components/ui/KanbanBoard";

type Filter = "open" | "done" | "all";
type View = "list" | "board";
type Cadence = "once" | RecurrenceRule;

function dueBadge(dueDate: string, t: (key: string, opts?: Record<string, unknown>) => string) {
  const today = new Date().toISOString().slice(0, 10);
  if (dueDate < today) {
    const days = Math.round((new Date(today).getTime() - new Date(dueDate).getTime()) / 86400000);
    return { variant: "danger" as const, label: t("tasks.dueOverdue", { count: days }) };
  }
  if (dueDate === today) {
    return { variant: "warning" as const, label: t("tasks.dueToday") };
  }
  return { variant: "default" as const, label: t("tasks.due", { date: dueDate }) };
}

export default function Tasks() {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [filter, setFilter] = useState<Filter>("open");
  const [view, setView] = useState<View>("list");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showNewTask, setShowNewTask] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDueDate, setNewDueDate] = useState("");
  const [newCadence, setNewCadence] = useState<Cadence>("once");
  const [creating, setCreating] = useState(false);

  const FILTER_LABELS: Record<Filter, string> = {
    open: t("tasks.filterOpen"),
    done: t("tasks.filterDone"),
    all: t("tasks.filterAll"),
  };

  const CADENCE_LABELS: Record<Cadence, string> = {
    once: t("tasks.cadenceOnce"),
    daily: t("tasks.cadenceDaily"),
    weekly: t("tasks.cadenceWeekly"),
    monthly: t("tasks.cadenceMonthly"),
  };

  const refresh = useCallback((currentView: View, currentFilter: Filter) => {
    setLoading(true);
    listTasks(currentView === "board" || currentFilter === "all" ? undefined : currentFilter)
      .then(setTasks)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("tasks.loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(() => {
    refresh(view, filter);
  }, [view, filter, refresh]);

  async function toggleDone(task: TaskOut) {
    const nextStatus = task.status === "done" ? "open" : "done";
    try {
      await updateTaskStatus(task.id, nextStatus);
      refresh(view, filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.updateError"));
    }
  }

  async function handleMove(taskId: string, status: TaskStatus, position: number) {
    try {
      await moveTask(taskId, status, position);
      refresh(view, filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.moveError"));
    }
  }

  function resetNewTaskForm() {
    setNewTitle("");
    setNewDueDate("");
    setNewCadence("once");
    setShowNewTask(false);
  }

  async function handleCreateTask() {
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      await createTask({
        title: newTitle.trim(),
        due_date: newDueDate || undefined,
        recurrence_rule: newCadence !== "once" && newDueDate ? newCadence : undefined,
      });
      resetNewTaskForm();
      refresh(view, filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.createError"));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-semibold text-ink">{t("tasks.title")}</h1>
        <div className="flex flex-wrap items-center gap-3">
          {view === "list" && (
            <div className="flex gap-1">
              {(["open", "done", "all"] as Filter[]).map((f) => (
                <Button key={f} size="sm" variant={filter === f ? "primary" : "ghost"} onClick={() => setFilter(f)}>
                  {FILTER_LABELS[f]}
                </Button>
              ))}
            </div>
          )}
          <div className="flex gap-1 border-l border-edge pl-3">
            {(["list", "board"] as View[]).map((v) => (
              <Button key={v} size="sm" variant={view === v ? "primary" : "ghost"} onClick={() => setView(v)}>
                {v === "list" ? t("tasks.viewList") : t("tasks.viewBoard")}
              </Button>
            ))}
          </div>
          {!showNewTask && (
            <Button size="sm" variant="secondary" onClick={() => setShowNewTask(true)}>
              {t("tasks.newTask")}
            </Button>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {showNewTask && (
        <Card className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-2" htmlFor="new-task-title">
              {t("tasks.newTaskTitleLabel")}
            </label>
            <input
              id="new-task-title"
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder={t("tasks.newTaskTitlePlaceholder")}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-ink-2" htmlFor="new-task-due">
                {t("tasks.dueDateLabel")}
              </label>
              <input
                id="new-task-due"
                type="date"
                value={newDueDate}
                onChange={(e) => setNewDueDate(e.target.value)}
                className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium text-ink-2">{t("tasks.repeatLabel")}</span>
              <div className="flex flex-wrap gap-1">
                {(["once", "daily", "weekly", "monthly"] as Cadence[]).map((c) => (
                  <Button
                    key={c}
                    size="sm"
                    variant={newCadence === c ? "primary" : "ghost"}
                    disabled={c !== "once" && !newDueDate}
                    onClick={() => setNewCadence(c)}
                  >
                    {CADENCE_LABELS[c]}
                  </Button>
                ))}
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={resetNewTaskForm}>
              {t("common.cancel")}
            </Button>
            <Button size="sm" variant="primary" onClick={handleCreateTask} disabled={creating || !newTitle.trim()}>
              {t("common.create")}
            </Button>
          </div>
        </Card>
      )}

      {loading ? (
        <p className="text-ink-3">{t("common.loading")}</p>
      ) : view === "board" ? (
        <KanbanBoard tasks={tasks} onMove={handleMove} />
      ) : tasks.length === 0 ? (
        <EmptyState message={t("tasks.emptyMessage", { filter: filter !== "all" ? FILTER_LABELS[filter] : "" })} />
      ) : (
        <div className="flex flex-col divide-y divide-edge rounded-2xl border border-edge bg-surface">
          {tasks.map((task) => {
            const badge = task.due_date ? dueBadge(task.due_date, t) : null;
            return (
              <div key={task.id} className="flex items-start gap-3 px-4 py-3">
                <input
                  type="checkbox"
                  checked={task.status === "done"}
                  onChange={() => toggleDone(task)}
                  className="mt-1 h-4 w-4 accent-accent"
                />
                <div className="flex-1">
                  <p className={task.status === "done" ? "text-sm text-ink-3 line-through" : "text-sm font-medium text-ink"}>
                    {task.title}
                    {task.recurrence_rule && (
                      <span className="ml-1.5 text-xs font-normal text-ink-3">↻ {CADENCE_LABELS[task.recurrence_rule]}</span>
                    )}
                  </p>
                  {task.description && <p className="mt-0.5 text-xs text-ink-2">{task.description}</p>}
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-3">
                    {badge && <Badge variant={badge.variant}>{badge.label}</Badge>}
                    {task.assignee && <span>{t("tasks.assignee", { name: task.assignee })}</span>}
                    {task.document_id && (
                      <Link to={`/documents/${task.document_id}`} className="hover:text-accent hover:underline">
                        {t("tasks.sourceDocument")}
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
