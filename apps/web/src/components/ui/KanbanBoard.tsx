import { useState, type DragEvent } from "react";
import type { TaskOut, TaskStatus } from "../../lib/api";

const COLUMNS: { status: TaskStatus; label: string }[] = [
  { status: "open", label: "To do" },
  { status: "in_progress", label: "In progress" },
  { status: "done", label: "Done" },
];

export function KanbanBoard({
  tasks,
  onMove,
}: {
  tasks: TaskOut[];
  onMove: (taskId: string, status: TaskStatus, position: number) => void;
}) {
  const [dragOverColumn, setDragOverColumn] = useState<TaskStatus | null>(null);

  const byColumn: Record<TaskStatus, TaskOut[]> = { open: [], in_progress: [], done: [] };
  for (const task of tasks) {
    const status = (task.status as TaskStatus) in byColumn ? (task.status as TaskStatus) : "open";
    byColumn[status].push(task);
  }
  for (const status of Object.keys(byColumn) as TaskStatus[]) {
    byColumn[status].sort((a, b) => a.position - b.position);
  }

  function dragStart(e: DragEvent<HTMLDivElement>, taskId: string) {
    e.dataTransfer.setData("text/plain", taskId);
    e.dataTransfer.effectAllowed = "move";
  }

  function dropOnCard(e: DragEvent<HTMLDivElement>, status: TaskStatus, index: number) {
    e.preventDefault();
    e.stopPropagation();
    setDragOverColumn(null);
    const taskId = e.dataTransfer.getData("text/plain");
    if (taskId) onMove(taskId, status, index);
  }

  function dropOnColumn(e: DragEvent<HTMLDivElement>, status: TaskStatus, length: number) {
    e.preventDefault();
    setDragOverColumn(null);
    const taskId = e.dataTransfer.getData("text/plain");
    if (taskId) onMove(taskId, status, length);
  }

  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
      {COLUMNS.map(({ status, label }) => {
        const columnTasks = byColumn[status];
        return (
          <div
            key={status}
            role="group"
            aria-label={label}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOverColumn(status);
            }}
            onDragLeave={() => setDragOverColumn((current) => (current === status ? null : current))}
            onDrop={(e) => dropOnColumn(e, status, columnTasks.length)}
            className={`min-h-[160px] rounded-2xl border border-edge p-2.5 transition-colors duration-fast ${
              dragOverColumn === status ? "bg-accent-soft" : "bg-bg"
            }`}
          >
            <h5 className="mb-2.5 flex items-center justify-between px-1.5 text-[11px] font-bold uppercase tracking-wide text-ink-3">
              <span>{label}</span>
              <span>{columnTasks.length}</span>
            </h5>
            {columnTasks.map((task, index) => (
              <div
                key={task.id}
                draggable
                onDragStart={(e) => dragStart(e, task.id)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => dropOnCard(e, status, index)}
                className="mb-2 cursor-grab rounded-xl border border-edge bg-surface p-2.5 text-[12.5px] shadow-raised active:cursor-grabbing"
              >
                <div className="font-semibold text-ink">{task.title}</div>
                {(task.due_date || task.assignee) && (
                  <div className="mt-1 text-[11px] text-ink-3">
                    {task.due_date ? `Due ${task.due_date}` : null}
                    {task.due_date && task.assignee ? " · " : null}
                    {task.assignee ?? null}
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
