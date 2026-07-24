import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { TaskDetailContent } from "./TaskDetailContent";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    updateTaskTitle: vi.fn(),
    updateTaskDescription: vi.fn(),
    updateTaskStatus: vi.fn(),
    updateTaskCategory: vi.fn(),
    downloadTaskIcs: vi.fn(),
  };
});

const TASK: api.TaskOut = {
  id: "t1", document_id: "d1", title: "Review lease", description: "Check clause",
  due_date: "2026-08-01", assignee: "Ada", status: "open", position: 0, source: "manual",
  created_at: "2026-01-01T00:00:00Z", recurrence_rule: null, category: "deadline",
};

function renderContent(task = TASK, onChanged = vi.fn()) {
  return render(
    <MemoryRouter>
      <TaskDetailContent task={task} onChanged={onChanged} />
    </MemoryRouter>
  );
}

describe("TaskDetailContent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the task title editable and shows its status pipeline", () => {
    renderContent();
    expect(screen.getByText("Review lease")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Toggle task status" })).toBeInTheDocument();
  });

  it("advancing the status pipeline calls updateTaskStatus with the next status and refreshes", async () => {
    vi.mocked(api.updateTaskStatus).mockResolvedValue({ ...TASK, status: "in_progress" });
    const onChanged = vi.fn();
    renderContent(TASK, onChanged);

    fireEvent.click(screen.getByRole("button", { name: "Toggle task status" }));

    await waitFor(() => expect(api.updateTaskStatus).toHaveBeenCalledWith("t1", "in_progress"));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it("wraps status from done back to open", async () => {
    vi.mocked(api.updateTaskStatus).mockResolvedValue({ ...TASK, status: "open" });
    renderContent({ ...TASK, status: "done" });

    fireEvent.click(screen.getByRole("button", { name: "Toggle task status" }));

    await waitFor(() => expect(api.updateTaskStatus).toHaveBeenCalledWith("t1", "open"));
  });

  it("changing the category select calls updateTaskCategory with the current status", async () => {
    vi.mocked(api.updateTaskCategory).mockResolvedValue({ ...TASK, category: "payment" });
    renderContent();

    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "payment" } });

    await waitFor(() => expect(api.updateTaskCategory).toHaveBeenCalledWith("t1", "open", "payment"));
  });

  it("clicking 'Add to calendar' downloads the task's ics", async () => {
    vi.mocked(api.downloadTaskIcs).mockResolvedValue(undefined);
    renderContent();

    fireEvent.click(screen.getByRole("button", { name: /add to calendar/i }));

    await waitFor(() => expect(api.downloadTaskIcs).toHaveBeenCalledWith("t1", "review-lease.ics"));
  });

  it("shows a link to the source document when present", () => {
    renderContent();
    expect(screen.getByRole("link", { name: "Source document" })).toHaveAttribute("href", "/documents/d1");
  });

  it("does not show a source document link when the task has none", () => {
    renderContent({ ...TASK, document_id: null });
    expect(screen.queryByRole("link", { name: "Source document" })).not.toBeInTheDocument();
  });
});
