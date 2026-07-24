import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  createTask,
  deleteTask,
  downloadTaskIcs,
  getTask,
  listTasks,
  moveTask,
  updateTaskCategory,
  updateTaskStatus,
  type RecurrenceRule,
  type TaskCategory,
  type TaskOut,
  type TaskStatus,
} from "../lib/api";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { ActivityTab } from "../components/ActivityTab";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { DeleteConfirmButton } from "../components/DeleteConfirmButton";
import { Drawer } from "../components/ui/Drawer";
import { KanbanBoard } from "../components/ui/KanbanBoard";
import { ShareButton } from "../components/ShareButton";
import { TaskDetailContent } from "../components/TaskDetailContent";
import { useDateFormat } from "../hooks/useDateFormat";
import { taskUrgency, relativeDueLabel } from "../lib/taskUrgency";
import { SkeletonLines } from "../components/ui/Skeleton";
import { useToast } from "../lib/toast";

type Filter = "open" | "done" | "all";
type View = "list" | "board";
type Cadence = "once" | RecurrenceRule;
type CategoryChoice = "" | TaskCategory;

const CATEGORIES: TaskCategory[] = ["payment", "appointment", "deadline", "notification"];

export default function Tasks() {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [selectedTask, setSelectedTask] = useState<TaskOut | null>(null);
  const [deletingTask, setDeletingTask] = useState(false);
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [filter, setFilter] = useState<Filter>("open");
  const [view, setView] = useState<View>("list");
  const [allTasks, setAllTasks] = useState<TaskOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showNewTask, setShowNewTask] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDueDate, setNewDueDate] = useState("");
  const [newCadence, setNewCadence] = useState<Cadence>("once");
  const [newCategory, setNewCategory] = useState<CategoryChoice>("");
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

  const CATEGORY_LABELS: Record<TaskCategory, string> = {
    payment: t("tasks.categoryPayment"),
    appointment: t("tasks.categoryAppointment"),
    deadline: t("tasks.categoryDeadline"),
    notification: t("tasks.categoryNotification"),
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

  useEffect(() => {
    listTasks().then(setAllTasks).catch(() => {});
  }, []);

  const loadSelectedTask = useCallback(() => {
    if (!id) return;
    getTask(id).then(setSelectedTask).catch(() => setSelectedTask(null));
  }, [id]);

  useEffect(() => {
    setSelectedTask(null);
    loadSelectedTask();
  }, [loadSelectedTask]);

  async function handleDrawerDeleteTask() {
    if (!id || !selectedTask) return;
    setDeletingTask(true);
    try {
      await deleteTask(id);
      showToast(t("tasks.deletedToast", { title: selectedTask.title }));
      navigate("/tasks");
      refresh(view, filter);
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : t("tasks.deleteError"));
    } finally {
      setDeletingTask(false);
    }
  }

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
    setNewCategory("");
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
        category: newCategory || undefined,
      });
      resetNewTaskForm();
      refresh(view, filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.createError"));
    } finally {
      setCreating(false);
    }
  }

  async function handleSetCategory(task: TaskOut, category: TaskCategory) {
    try {
      await updateTaskCategory(task.id, task.status as TaskStatus, category);
      refresh(view, filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.updateError"));
    }
  }

  async function handleDownloadIcs(task: TaskOut) {
    const slug = task.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "task";
    try {
      await downloadTaskIcs(task.id, `${slug}.ics`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.calendarError"));
    }
  }

  const openTasks = allTasks.filter((task) => task.status !== "done");
  const overdueCount = openTasks.filter((task) => task.due_date && taskUrgency(task.due_date).variant === "danger").length;
  const dueTodayCount = openTasks.filter((task) => task.due_date && taskUrgency(task.due_date).variant === "warning").length;

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

      <div className="flex flex-wrap gap-3">
        <Card className="flex flex-col gap-0.5 px-4 py-2.5">
          <span className="text-xs text-ink-3">{t("tasks.statsOpenLabel")}</span>
          <span data-testid="stat-open-count" className="text-lg font-semibold text-ink">{openTasks.length}</span>
        </Card>
        <Card className="flex flex-col gap-0.5 px-4 py-2.5">
          <span className="text-xs text-ink-3">{t("tasks.statsOverdueLabel")}</span>
          <span data-testid="stat-overdue-count" className={`text-lg font-semibold ${overdueCount > 0 ? "text-danger" : "text-ink"}`}>{overdueCount}</span>
        </Card>
        <Card className="flex flex-col gap-0.5 px-4 py-2.5">
          <span className="text-xs text-ink-3">{t("tasks.statsDueTodayLabel")}</span>
          <span data-testid="stat-due-today-count" className={`text-lg font-semibold ${dueTodayCount > 0 ? "text-warning" : "text-ink"}`}>{dueTodayCount}</span>
        </Card>
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
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-ink-2" htmlFor="new-task-category">
                {t("tasks.categoryLabel")}
              </label>
              <select
                id="new-task-category"
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value as CategoryChoice)}
                className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
              >
                <option value="">{t("tasks.categoryNone")}</option>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORY_LABELS[c]}
                  </option>
                ))}
              </select>
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
        <SkeletonLines />
      ) : view === "board" ? (
        <KanbanBoard tasks={tasks} onMove={handleMove} formatDate={formatDate} />
      ) : tasks.length === 0 ? (
        <EmptyState message={t("tasks.emptyMessage", { filter: filter !== "all" ? FILTER_LABELS[filter] : "" })} />
      ) : (
        <div className="flex flex-col divide-y divide-edge rounded-2xl border border-edge bg-surface">
          {tasks.map((task) => {
            const badge = task.due_date
              ? { variant: taskUrgency(task.due_date).variant, label: relativeDueLabel(task.due_date, t, formatDate) }
              : null;
            return (
              <div
                key={task.id}
                data-testid="task-row"
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/tasks/${task.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") navigate(`/tasks/${task.id}`);
                }}
                className={`flex cursor-pointer items-start gap-3 border-l-2 px-4 py-3 ${
                  task.due_date && task.status !== "done"
                    ? { danger: "border-l-danger", warning: "border-l-warning", default: "border-l-transparent" }[taskUrgency(task.due_date).variant]
                    : "border-l-transparent"
                }`}
              >
                <input
                  type="checkbox"
                  checked={task.status === "done"}
                  onChange={() => toggleDone(task)}
                  onClick={(event) => event.stopPropagation()}
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
                      <Link
                        to={`/documents/${task.document_id}`}
                        onClick={(event) => event.stopPropagation()}
                        className="hover:text-accent hover:underline"
                      >
                        {t("tasks.sourceDocument")}
                      </Link>
                    )}
                    {task.due_date && (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          handleDownloadIcs(task);
                        }}
                        className="hover:text-accent hover:underline"
                      >
                        {t("tasks.addToCalendar")}
                      </button>
                    )}
                    <select
                      aria-label={`${t("tasks.categoryLabel")} – ${task.title}`}
                      value={task.category ?? ""}
                      onChange={(e) => handleSetCategory(task, e.target.value as TaskCategory)}
                      onClick={(event) => event.stopPropagation()}
                      className="rounded border border-edge bg-surface px-1 py-0.5 text-xs text-ink-3 outline-none focus:border-accent"
                    >
                      <option value="" disabled>
                        {t("tasks.categoryLabel")}
                      </option>
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {CATEGORY_LABELS[c]}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Drawer
        open={!!id}
        onClose={() => navigate("/tasks")}
        title={selectedTask?.title ?? ""}
        tabs={[
          {
            id: "details",
            label: t("drawer.details"),
            content: selectedTask ? (
              <TaskDetailContent task={selectedTask} onChanged={loadSelectedTask} />
            ) : (
              <SkeletonLines />
            ),
          },
          {
            id: "activity",
            label: t("drawer.activity"),
            content: id ? <ActivityTab entityType="task" entityId={id} /> : null,
          },
        ]}
        footer={
          id && (
            <>
              <ShareButton entityType="task" entityId={id} />
              <DeleteConfirmButton
                confirmTitle={t("tasks.deleteModalTitle", { title: selectedTask?.title ?? "" })}
                confirmBody={t("tasks.deleteModalBody")}
                confirmLabel={t("tasks.deleteConfirm")}
                onConfirm={handleDrawerDeleteTask}
                deleting={deletingTask}
              />
            </>
          )
        }
      />
    </div>
  );
}
