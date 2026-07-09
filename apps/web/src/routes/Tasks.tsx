import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listTasks, moveTask, updateTaskStatus, type TaskOut, type TaskStatus } from "../lib/api";
import { Button } from "../components/ui/Button";
import { KanbanBoard } from "../components/ui/KanbanBoard";

type Filter = "open" | "done" | "all";
type View = "list" | "board";

export default function Tasks() {
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [filter, setFilter] = useState<Filter>("open");
  const [view, setView] = useState<View>("list");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((currentView: View, currentFilter: Filter) => {
    setLoading(true);
    listTasks(currentView === "board" || currentFilter === "all" ? undefined : currentFilter)
      .then(setTasks)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load tasks"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh(view, filter);
  }, [view, filter, refresh]);

  async function toggleDone(task: TaskOut) {
    const nextStatus = task.status === "done" ? "open" : "done";
    try {
      await updateTaskStatus(task.id, nextStatus);
      refresh(view, filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update task");
    }
  }

  async function handleMove(taskId: string, status: TaskStatus, position: number) {
    try {
      await moveTask(taskId, status, position);
      refresh(view, filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to move task");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">Tasks</h1>
        <div className="flex items-center gap-3">
          {view === "list" && (
            <div className="flex gap-1">
              {(["open", "done", "all"] as Filter[]).map((f) => (
                <Button key={f} size="sm" variant={filter === f ? "primary" : "ghost"} onClick={() => setFilter(f)}>
                  {f}
                </Button>
              ))}
            </div>
          )}
          <div className="flex gap-1 border-l border-edge pl-3">
            {(["list", "board"] as View[]).map((v) => (
              <Button key={v} size="sm" variant={view === v ? "primary" : "ghost"} onClick={() => setView(v)}>
                {v === "list" ? "List" : "Board"}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {loading ? (
        <p className="text-ink-3">Loading…</p>
      ) : view === "board" ? (
        <KanbanBoard tasks={tasks} onMove={handleMove} />
      ) : tasks.length === 0 ? (
        <p className="text-ink-3">No {filter !== "all" ? filter : ""} tasks.</p>
      ) : (
        <div className="flex flex-col divide-y divide-edge rounded-2xl border border-edge bg-surface">
          {tasks.map((task) => (
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
                </p>
                {task.description && <p className="mt-0.5 text-xs text-ink-2">{task.description}</p>}
                <div className="mt-1 flex gap-3 text-xs text-ink-3">
                  {task.due_date && <span>Due {task.due_date}</span>}
                  {task.assignee && <span>Assignee: {task.assignee}</span>}
                  {task.document_id && (
                    <Link to={`/documents/${task.document_id}`} className="hover:text-accent hover:underline">
                      Source document
                    </Link>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
