import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Tasks from "./Tasks";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listTasks: vi.fn(),
    updateTaskStatus: vi.fn(),
    moveTask: vi.fn(),
  };
});

const OPEN_TASKS: api.TaskOut[] = [
  {
    id: "t1", document_id: "d1", title: "Review lease", description: "Check termination clause",
    due_date: "2026-08-01", assignee: "Ada", status: "open", position: 0, source: "manual", created_at: "2026-01-01T00:00:00Z",
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <Tasks />
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
    expect(screen.getByText("Due 2026-08-01")).toBeInTheDocument();
    expect(screen.getByText("Assignee: Ada")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Source document" })).toHaveAttribute("href", "/documents/d1");
  });

  it("defaults to the open filter and re-queries when a different tab is clicked", async () => {
    renderPage();
    await screen.findByText("Review lease");
    expect(api.listTasks).toHaveBeenLastCalledWith("open");
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
});
