import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { KanbanBoard } from "./KanbanBoard";
import type { TaskOut } from "../../lib/api";

function task(overrides: Partial<TaskOut>): TaskOut {
  return {
    id: "t1",
    document_id: null,
    title: "Untitled",
    description: null,
    due_date: null,
    assignee: null,
    status: "open",
    position: 0,
    source: "manual",
    created_at: "2026-07-01T00:00:00Z",
    ...overrides,
  };
}

function makeDataTransfer(taskId: string) {
  const store: Record<string, string> = {};
  return {
    setData: (_type: string, value: string) => {
      store[_type] = value;
    },
    getData: () => taskId,
    effectAllowed: "",
  };
}

describe("KanbanBoard", () => {
  it("renders three columns with cards grouped by status, ordered by position", () => {
    const tasks = [
      task({ id: "a", title: "Chase invoice", status: "open", position: 1 }),
      task({ id: "b", title: "Confirm APK", status: "open", position: 0 }),
      task({ id: "c", title: "Draft response", status: "in_progress", position: 0 }),
      task({ id: "d", title: "Upload policy", status: "done", position: 0 }),
    ];
    render(<KanbanBoard tasks={tasks} onMove={() => {}} />);

    expect(screen.getByRole("group", { name: "To do" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "In progress" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Done" })).toBeInTheDocument();

    const todoColumn = screen.getByRole("group", { name: "To do" });
    const titles = Array.from(todoColumn.querySelectorAll(".font-semibold")).map((el) => el.textContent);
    expect(titles).toEqual(["Confirm APK", "Chase invoice"]);
  });

  it("shows due date and assignee meta when present", () => {
    const tasks = [task({ due_date: "2026-08-01", assignee: "Alice" })];
    render(<KanbanBoard tasks={tasks} onMove={() => {}} />);
    expect(screen.getByText("Due 2026-08-01 · Alice")).toBeInTheDocument();
  });

  it("calls onMove with the target column's length when dropped on the column background", () => {
    const onMove = vi.fn();
    const tasks = [
      task({ id: "a", title: "Task A", status: "open", position: 0 }),
      task({ id: "b", title: "Task B", status: "in_progress", position: 0 }),
    ];
    render(<KanbanBoard tasks={tasks} onMove={onMove} />);

    const inProgressColumn = screen.getByRole("group", { name: "In progress" });
    const dataTransfer = makeDataTransfer("a");
    const dropEvent = new Event("drop", { bubbles: true, cancelable: true }) as unknown as DragEvent;
    Object.defineProperty(dropEvent, "dataTransfer", { value: dataTransfer });
    inProgressColumn.dispatchEvent(dropEvent);

    expect(onMove).toHaveBeenCalledWith("a", "in_progress", 1);
  });

  it("calls onMove with the hovered card's index when dropped directly on a card", () => {
    const onMove = vi.fn();
    const tasks = [
      task({ id: "a", title: "Task A", status: "open", position: 0 }),
      task({ id: "b", title: "Task B", status: "open", position: 1 }),
      task({ id: "c", title: "Task C", status: "in_progress", position: 0 }),
    ];
    render(<KanbanBoard tasks={tasks} onMove={onMove} />);

    const targetCard = screen.getByText("Task B").closest("[draggable]") as HTMLElement;
    const dataTransfer = makeDataTransfer("c");
    const dropEvent = new Event("drop", { bubbles: true, cancelable: true }) as unknown as DragEvent;
    Object.defineProperty(dropEvent, "dataTransfer", { value: dataTransfer });
    targetCard.dispatchEvent(dropEvent);

    expect(onMove).toHaveBeenCalledWith("c", "open", 1);
  });

  it("treats an unknown status as the 'open' column rather than dropping the task", () => {
    const tasks = [task({ id: "a", title: "Weird status task", status: "archived" })];
    render(<KanbanBoard tasks={tasks} onMove={() => {}} />);
    const todoColumn = screen.getByRole("group", { name: "To do" });
    expect(todoColumn).toHaveTextContent("Weird status task");
  });
});
