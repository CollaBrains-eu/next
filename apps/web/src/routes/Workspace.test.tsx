import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Workspace from "./Workspace";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listDocuments: vi.fn(),
    listCategories: vi.fn(),
    search: vi.fn(),
    deleteDocument: vi.fn(),
  };
});

const docs: api.DocumentOut[] = Array.from({ length: 12 }, (_, i) => ({
  id: `doc-${i}`,
  title: `document-${i}.pdf`,
  filename: `document-${i}.pdf`,
  mime_type: "application/pdf",
  status: i === 0 ? "failed" : "ready",
  error: null,
  created_at: "2026-07-08T19:11:38Z",
  processed_at: "2026-07-08T19:12:00Z",
  category_id: null,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <Workspace />
      </ToastProvider>
    </MemoryRouter>
  );
}

describe("Workspace (Documents list)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listDocuments).mockResolvedValue(docs);
    vi.mocked(api.listCategories).mockResolvedValue([]);
  });

  it("renders documents in a paginated DataTable (only 10 of 12 rows visible on page 1)", async () => {
    renderPage();
    expect(await screen.findByText("document-0.pdf")).toBeInTheDocument();
    expect(screen.queryByText("document-11.pdf")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "2" })).toBeInTheDocument();
  });

  it("shows a status badge per row", async () => {
    renderPage();
    await screen.findByText("document-0.pdf");
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getAllByText("ready").length).toBeGreaterThan(0);
  });

  it("shows the redesigned EmptyState when there are no documents", async () => {
    vi.mocked(api.listDocuments).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument();
  });

  it("shows a status filter chip for 'failed' documents, and toggling it narrows the table to just that row", async () => {
    renderPage();
    await screen.findByText("document-0.pdf");
    fireEvent.click(screen.getByText("+ Add filter"));
    fireEvent.click(screen.getByText("Status: Failed"));
    expect(screen.getByText("document-0.pdf")).toBeInTheDocument();
    expect(screen.queryByText("document-1.pdf")).not.toBeInTheDocument();
  });

  it("removing an active filter chip restores the full table", async () => {
    renderPage();
    await screen.findByText("document-0.pdf");
    fireEvent.click(screen.getByText("+ Add filter"));
    fireEvent.click(screen.getByText("Status: Failed"));
    fireEvent.click(screen.getByLabelText("Remove Status: Failed"));
    expect(screen.getByText("document-1.pdf")).toBeInTheDocument();
  });

  it("selecting rows shows the bulk action bar with the right count", async () => {
    renderPage();
    await screen.findByText("document-0.pdf");
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    expect(screen.getByText((_, el) => el?.textContent === "2 selected")).toBeInTheDocument();
  });

  it("shows a category filter chip and toggling it narrows the table to matching documents", async () => {
    vi.mocked(api.listCategories).mockResolvedValue([
      { id: "cat-1", slug: "payslip", icon: "Banknote", color: "#FF9500", parent_id: null },
      { id: "cat-2", slug: "invoice", icon: "Receipt", color: "#FF3B30", parent_id: null },
    ]);
    vi.mocked(api.listDocuments).mockResolvedValue([
      { ...docs[0], category_id: "cat-1" },
      { ...docs[1], category_id: "cat-2" },
    ]);
    renderPage();
    await screen.findByText("document-0.pdf");
    await waitFor(() => expect(screen.getAllByText("+ Add filter")).toHaveLength(2));
    fireEvent.click(screen.getAllByText("+ Add filter")[1]);
    fireEvent.click(await screen.findByText("Payslip & Salary"));
    expect(screen.getByText("document-0.pdf")).toBeInTheDocument();
    expect(screen.queryByText("document-1.pdf")).not.toBeInTheDocument();
  });

  it("removing an active category filter chip restores the full table", async () => {
    vi.mocked(api.listCategories).mockResolvedValue([
      { id: "cat-1", slug: "payslip", icon: "Banknote", color: "#FF9500", parent_id: null },
      { id: "cat-2", slug: "invoice", icon: "Receipt", color: "#FF3B30", parent_id: null },
    ]);
    vi.mocked(api.listDocuments).mockResolvedValue([
      { ...docs[0], category_id: "cat-1" },
      { ...docs[1], category_id: "cat-2" },
    ]);
    renderPage();
    await screen.findByText("document-0.pdf");
    await waitFor(() => expect(screen.getAllByText("+ Add filter")).toHaveLength(2));
    fireEvent.click(screen.getAllByText("+ Add filter")[1]);
    fireEvent.click(await screen.findByText("Payslip & Salary"));
    fireEvent.click(screen.getByLabelText("Remove Payslip & Salary"));
    expect(screen.getByText("document-1.pdf")).toBeInTheDocument();
  });

  it("bulk-deleting selected rows calls deleteDocument for each and shows a toast", async () => {
    vi.mocked(api.deleteDocument).mockResolvedValue(undefined);
    renderPage();
    await screen.findByText("document-0.pdf");
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(api.deleteDocument).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/deleted/i)).toBeInTheDocument();
  });
});
