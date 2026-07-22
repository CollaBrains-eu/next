import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  downloadTaskIcs,
  updateTaskCategory,
  updateTaskDescription,
  updateTaskStatus,
  updateTaskTitle,
  type TaskCategory,
  type TaskOut,
  type TaskStatus,
} from "../lib/api";
import { useState } from "react";
import { useDateFormat } from "../hooks/useDateFormat";
import { InlineEditableText } from "./ui/InlineEditableText";
import { StatusPipeline, type StatusStage } from "./ui/StatusPipeline";
import { Tooltip } from "./ui/Tooltip";
import { Alert } from "./ui/Alert";

const CATEGORIES: TaskCategory[] = ["payment", "appointment", "deadline", "notification"];
const STATUS_ORDER: TaskStatus[] = ["open", "in_progress", "done"];

function nextTaskStatus(current: TaskStatus): TaskStatus {
  return STATUS_ORDER[(STATUS_ORDER.indexOf(current) + 1) % STATUS_ORDER.length];
}

export function TaskDetailContent({ task, onChanged }: { task: TaskOut; onChanged: () => void }) {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
  const [error, setError] = useState<string | null>(null);

  const stages: StatusStage[] = [
    { key: "open", label: t("tasks.filterOpen") },
    { key: "in_progress", label: t("tasks.statusInProgress") },
    { key: "done", label: t("tasks.filterDone") },
  ];

  async function handleTitleSave(title: string) {
    try {
      await updateTaskTitle(task.id, task.status as TaskStatus, title);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.updateError"));
    }
  }

  async function handleDescriptionSave(description: string) {
    try {
      await updateTaskDescription(task.id, task.status as TaskStatus, description);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.updateError"));
    }
  }

  async function handleAdvanceStatus() {
    try {
      await updateTaskStatus(task.id, nextTaskStatus(task.status as TaskStatus));
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.updateError"));
    }
  }

  async function handleSetCategory(category: TaskCategory) {
    try {
      await updateTaskCategory(task.id, task.status as TaskStatus, category);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.updateError"));
    }
  }

  async function handleDownloadIcs() {
    const slug = task.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "task";
    try {
      await downloadTaskIcs(task.id, `${slug}.ics`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("tasks.calendarError"));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <Alert variant="danger" dismissible onDismiss={() => setError(null)}>{error}</Alert>}

      <h2 className="text-lg font-semibold text-ink">
        <InlineEditableText value={task.title} onSave={handleTitleSave} />
      </h2>

      <Tooltip label={t("tasks.statusLabel")}>
        <button
          onClick={handleAdvanceStatus}
          className="w-fit rounded-full"
          aria-label={t("tasks.statusLabel")}
        >
          <StatusPipeline stages={stages} currentKey={task.status} />
        </button>
      </Tooltip>

      <div>
        <span className="text-xs font-medium text-ink-2">{t("tasks.newTaskTitleLabel")}</span>
        <p className="mt-1 text-sm text-ink">
          <InlineEditableText value={task.description ?? ""} onSave={handleDescriptionSave} />
        </p>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-ink-2" htmlFor="task-detail-category">
          {t("tasks.categoryLabel")}
        </label>
        <select
          id="task-detail-category"
          value={task.category ?? ""}
          onChange={(e) => handleSetCategory(e.target.value as TaskCategory)}
          className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
        >
          <option value="" disabled>
            {t("tasks.categoryNone")}
          </option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {t(`tasks.category${c.charAt(0).toUpperCase()}${c.slice(1)}`)}
            </option>
          ))}
        </select>
      </div>

      {task.due_date && (
        <div className="flex items-center justify-between gap-2 text-sm">
          <span className="text-ink-2">{t("tasks.dueDateLabel")}: {formatDate(task.due_date)}</span>
          <button type="button" onClick={handleDownloadIcs} className="text-xs text-ink-3 hover:text-accent hover:underline">
            {t("tasks.addToCalendar")}
          </button>
        </div>
      )}

      {task.assignee && <p className="text-sm text-ink-2">{t("tasks.assignee", { name: task.assignee })}</p>}

      {task.document_id && (
        <Link to={`/documents/${task.document_id}`} className="text-sm text-ink-3 hover:text-accent hover:underline">
          {t("tasks.sourceDocument")}
        </Link>
      )}
    </div>
  );
}
