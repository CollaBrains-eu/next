import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listTasks, updateTaskStatus, type TaskOut } from "../lib/api";

type Filter = "open" | "done" | "all";

export default function Tasks() {
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [filter, setFilter] = useState<Filter>("open");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((currentFilter: Filter) => {
    setLoading(true);
    listTasks(currentFilter === "all" ? undefined : currentFilter)
      .then(setTasks)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load tasks"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh(filter);
  }, [filter, refresh]);

  async function toggleDone(task: TaskOut) {
    const nextStatus = task.status === "done" ? "open" : "done";
    try {
      await updateTaskStatus(task.id, nextStatus);
      refresh(filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update task");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Tasks</h1>
        <div className="flex gap-1 text-sm">
          {(["open", "done", "all"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded px-3 py-1 ${
                filter === f ? "bg-slate-900 text-white" : "text-slate-500 hover:bg-slate-100"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : tasks.length === 0 ? (
        <p className="text-slate-500">No {filter !== "all" ? filter : ""} tasks.</p>
      ) : (
        <div className="flex flex-col divide-y divide-slate-200 rounded border border-slate-200 bg-white">
          {tasks.map((task) => (
            <div key={task.id} className="flex items-start gap-3 px-4 py-3">
              <input
                type="checkbox"
                checked={task.status === "done"}
                onChange={() => toggleDone(task)}
                className="mt-1"
              />
              <div className="flex-1">
                <p className={task.status === "done" ? "text-sm text-slate-400 line-through" : "text-sm font-medium"}>
                  {task.title}
                </p>
                {task.description && <p className="mt-0.5 text-xs text-slate-500">{task.description}</p>}
                <div className="mt-1 flex gap-3 text-xs text-slate-400">
                  {task.due_date && <span>Due {task.due_date}</span>}
                  {task.assignee && <span>Assignee: {task.assignee}</span>}
                  {task.document_id && (
                    <Link to={`/documents/${task.document_id}`} className="hover:text-slate-900 hover:underline">
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
