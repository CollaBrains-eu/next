import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Tasks from "./Tasks";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listTasks: vi.fn(),
    createTask: vi.fn(),
    updateTaskStatus: vi.fn(),
    moveTask: vi.fn(),
    updateTaskCategory: vi.fn(),
    downloadTaskIcs: vi.fn(),
    getTask: vi.fn(),
    deleteTask: vi.fn(),
  };
});

function isoDate(offsetDays: number): string {
  return new Date(Date.now() + offsetDays * 86400000).toISOString().slice(0, 10);
}

const OPEN_TASKS: api.TaskOut[] = [
  {
    id: "t1", document_id: "d1", title: "Review lease", description: "Check termination clause",
    due_date: "2026-08-01", assignee: "Ada", status: "open", position: 0, source: "manual",
    created_at: "2026-01-01T00:00:00Z", recurrence_rule: null, category: null,
  },
];

function renderPage(initialPath = "/tasks") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ToastProvider>
        <Routes>
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/tasks/:id" element={<Tasks />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  );
}

describe("Tasks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listTasks).mockResolvedValue(OPEN_TASKS);
    vi.mocked(api.updateTaskStatus).mockResolvedValue({ ...OPEN_TASKS[0], status: "done" });
  });

  it("renders open tasks with their metadata and source-document link", async () => {
    renderPage();
    expect(await screen.findByText("Review lease")).toBeInTheDocument();
    expect(screen.getByText("Check termination clause")).toBeInTheDocument();
    expect(screen.getByText("Due 01/08/2026")).toBeInTheDocument();
    expect(screen.getByText("Assignee: Ada")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Source document" })).toHaveAttribute("href", "/documents/d1");
  });

  it("defaults to the open filter and re-queries when a different tab is clicked", async () => {
    renderPage();
    await screen.findByText("Review lease");
    expect(api.listTasks).toHaveBeenCalledWith("open");
    fireEvent.click(screen.getByRole("button", { name: "done" }));
    await waitFor(() => expect(api.listTasks).toHaveBeenLastCalledWith("done"));
  });

  it("toggles a task's done status when its checkbox is clicked", async () => {
    renderPage();
    await screen.findByText("Review lease");
    fireEvent.click(screen.getByRole("checkbox"));
    await waitFor(() => expect(api.updateTaskStatus).toHaveBeenCalledWith("t1", "done"));
  });

  it("shows an empty message when there are no tasks", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No open tasks.")).toBeInTheDocument();
  });

  it("switching to Board fetches all tasks (no status filter) and renders the Kanban board", async () => {
    renderPage();
    await screen.findByText("Review lease");
    fireEvent.click(screen.getByRole("button", { name: "Board" }));
    await waitFor(() => expect(api.listTasks).toHaveBeenLastCalledWith(undefined));
    expect(await screen.findByRole("group", { name: "To do" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("hides the open/done/all filter tabs while in Board view", async () => {
    renderPage();
    await screen.findByText("Review lease");
    fireEvent.click(screen.getByRole("button", { name: "Board" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "done" })).not.toBeInTheDocument());
  });

  it("shows a danger overdue badge for a past due date", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: isoDate(-2) }]);
    renderPage();
    expect(await screen.findByText("Overdue by 2 days")).toBeInTheDocument();
  });

  it("shows a due-today badge for today's due date", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: isoDate(0) }]);
    renderPage();
    expect(await screen.findByText("Due today")).toBeInTheDocument();
  });

  it("shows 'Due tomorrow' for a task due the next day", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: isoDate(1) }]);
    renderPage();
    expect(await screen.findByText("Due tomorrow")).toBeInTheDocument();
  });

  it("shows 'Due in N days' for a task due within a week", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: isoDate(4) }]);
    renderPage();
    expect(await screen.findByText("Due in 4 days")).toBeInTheDocument();
  });


  it("shows a recurrence marker next to a recurring task's title", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], recurrence_rule: "weekly" }]);
    renderPage();
    expect(await screen.findByText("↻ Weekly")).toBeInTheDocument();
  });

  it("shows open/overdue/due-today counts in the stats strip, independent of the active filter tab", async () => {
    vi.mocked(api.listTasks).mockImplementation((statusFilter?: string) => {
      if (statusFilter === "open") return Promise.resolve([OPEN_TASKS[0]]);
      // unfiltered call (for the stats strip) sees the full mixed set
      return Promise.resolve([
        { ...OPEN_TASKS[0], id: "t1", status: "open", due_date: isoDate(-1) }, // overdue
        { ...OPEN_TASKS[0], id: "t2", status: "open", due_date: isoDate(0) }, // due today
        { ...OPEN_TASKS[0], id: "t3", status: "in_progress", due_date: isoDate(10) }, // open, not urgent
        { ...OPEN_TASKS[0], id: "t4", status: "done", due_date: isoDate(-5) }, // done, excluded
      ]);
    });
    renderPage();
    await screen.findByText("Review lease");
    // wait for the allTasks fetch to resolve and re-render before asserting counts
    await waitFor(() => expect(screen.getByTestId("stat-open-count")).toHaveTextContent("3"));
    expect(screen.getByTestId("stat-overdue-count")).toHaveTextContent("1");
    expect(screen.getByTestId("stat-due-today-count")).toHaveTextContent("1");
  });

  it("gives an overdue task's row a danger-colored left border", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: isoDate(-1) }]);
    renderPage();
    const row = (await screen.findByText("Review lease")).closest("[data-testid='task-row']");
    expect(row).toHaveClass("border-l-danger");
  });

  it("gives a task with no due date a transparent left border", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: null }]);
    renderPage();
    const row = (await screen.findByText("Review lease")).closest("[data-testid='task-row']");
    expect(row).toHaveClass("border-l-transparent");
  });

  it("gives a done task a transparent left border even with a past due date", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: isoDate(-1), status: "done" }]);
    renderPage();
    const row = (await screen.findByText("Review lease")).closest("[data-testid='task-row']");
    expect(row).toHaveClass("border-l-transparent");
  });


  it("opens the new-task form, disables recurrence chips until a due date is set, and submits", async () => {
    vi.mocked(api.createTask).mockResolvedValue({ ...OPEN_TASKS[0], id: "t2", title: "Chase invoice" });
    renderPage();
    await screen.findByText("Review lease");

    fireEvent.click(screen.getByRole("button", { name: "+ New task" }));
    expect(screen.getByRole("button", { name: "Weekly" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("What needs to happen?"), { target: { value: "Chase invoice" } });
    fireEvent.change(screen.getByLabelText("Due date"), { target: { value: "2026-08-15" } });
    expect(screen.getByRole("button", { name: "Weekly" })).not.toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Weekly" }));

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(api.createTask).toHaveBeenCalledWith({
        title: "Chase invoice",
        due_date: "2026-08-15",
        recurrence_rule: "weekly",
      })
    );
    // form closes and the list re-fetches after a successful create
    await waitFor(() => expect(screen.queryByLabelText("What needs to happen?")).not.toBeInTheDocument());
    expect(api.listTasks).toHaveBeenCalledTimes(3);
  });

  it("does not submit the new-task form with a blank title", async () => {
    renderPage();
    await screen.findByText("Review lease");
    fireEvent.click(screen.getByRole("button", { name: "+ New task" }));
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
    expect(api.createTask).not.toHaveBeenCalled();
  });

  it("cancelling the new-task form discards input and closes it", async () => {
    renderPage();
    await screen.findByText("Review lease");
    fireEvent.click(screen.getByRole("button", { name: "+ New task" }));
    fireEvent.change(screen.getByLabelText("What needs to happen?"), { target: { value: "Discard me" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText("What needs to happen?")).not.toBeInTheDocument();
    expect(api.createTask).not.toHaveBeenCalled();
  });

  it("includes the chosen category when submitting the new-task form", async () => {
    vi.mocked(api.createTask).mockResolvedValue({ ...OPEN_TASKS[0], id: "t2", title: "Pay rent" });
    renderPage();
    await screen.findByText("Review lease");

    fireEvent.click(screen.getByRole("button", { name: "+ New task" }));
    fireEvent.change(screen.getByLabelText("What needs to happen?"), { target: { value: "Pay rent" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "payment" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(api.createTask).toHaveBeenCalledWith({
        title: "Pay rent",
        due_date: undefined,
        recurrence_rule: undefined,
        category: "payment",
      })
    );
  });

  it("changing a task row's category select calls updateTaskCategory", async () => {
    vi.mocked(api.updateTaskCategory).mockResolvedValue({ ...OPEN_TASKS[0], category: "deadline" });
    renderPage();
    await screen.findByText("Review lease");

    fireEvent.change(screen.getByLabelText("Category – Review lease"), { target: { value: "deadline" } });

    await waitFor(() => expect(api.updateTaskCategory).toHaveBeenCalledWith("t1", "open", "deadline"));
  });

  it("clicking 'Add to calendar' on a task with a due date downloads its ics", async () => {
    vi.mocked(api.downloadTaskIcs).mockResolvedValue(undefined);
    renderPage();
    await screen.findByText("Review lease");

    fireEvent.click(screen.getByRole("button", { name: "📅 Add to calendar" }));

    await waitFor(() => expect(api.downloadTaskIcs).toHaveBeenCalledWith("t1", "review-lease.ics"));
  });

  it("does not show the 'Add to calendar' action for a task with no due date", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: null }]);
    renderPage();
    await screen.findByText("Review lease");
    expect(screen.queryByRole("button", { name: "📅 Add to calendar" })).not.toBeInTheDocument();
  });

  it("clicking a task row navigates to its detail route and opens the drawer with fetched task data", async () => {
    vi.mocked(api.getTask).mockResolvedValue(OPEN_TASKS[0]);
    renderPage();
    const row = await screen.findByTestId("task-row");
    fireEvent.click(row);
    await waitFor(() => expect(api.getTask).toHaveBeenCalledWith("t1"));
    expect(await screen.findByTestId("drawer-backdrop")).toBeInTheDocument();
  });

  it("clicking a task row's checkbox does not navigate to its detail route", async () => {
    renderPage();
    await screen.findByText("Review lease");
    fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.queryByTestId("drawer-backdrop")).not.toBeInTheDocument();
    expect(api.getTask).not.toHaveBeenCalled();
  });

  it("deleting a task from the drawer calls deleteTask and closes the drawer", async () => {
    vi.mocked(api.getTask).mockResolvedValue(OPEN_TASKS[0]);
    vi.mocked(api.deleteTask).mockResolvedValue(undefined);
    renderPage("/tasks/t1");
    await screen.findByTestId("drawer-backdrop");

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete task" }));

    await waitFor(() => expect(api.deleteTask).toHaveBeenCalledWith("t1"));
    await waitFor(() => expect(screen.queryByTestId("drawer-backdrop")).not.toBeInTheDocument());
  });
});
