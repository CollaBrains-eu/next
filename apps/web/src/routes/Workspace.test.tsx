import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import Workspace from "./Workspace";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin", role: "admin" } }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listDocuments: vi.fn(),
    listCategories: vi.fn(),
    listWorkspacesSharedWithMe: vi.fn(),
    search: vi.fn(),
    deleteDocument: vi.fn(),
    downloadDocumentsCsv: vi.fn(),
    getDocument: vi.fn(),
  };
});

const docs: api.DocumentOut[] = Array.from({ length: 12 }, (_, i) => ({
  id: `doc-${i}`,
  title: `document-${i}.pdf`,
  filename: `document-${i}.pdf`,
  mime_type: "application/pdf",
  status: i === 0 ? "failed" : "ready",
  error: null,
  doc_type: null,
  tags: [],
  correspondent: null,
  created_at: "2026-07-08T19:11:38Z",
  processed_at: "2026-07-08T19:12:00Z",
  category_id: null,
}));

function renderPage(initialPath = "/documents") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ToastProvider>
        <Routes>
          <Route path="/documents" element={<Workspace />} />
          <Route path="/documents/:id" element={<Workspace />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  );
}

describe("Workspace (Documents list)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listDocuments).mockResolvedValue(docs);
    vi.mocked(api.listCategories).mockResolvedValue([]);
    vi.mocked(api.listWorkspacesSharedWithMe).mockResolvedValue([]);
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

  it("toggling a child category chip narrows the table to matching documents", async () => {
    vi.mocked(api.listCategories).mockResolvedValue([
      { id: "parent-finance", slug: "finance", icon: "Coins", color: "#FF9500", parent_id: null },
      { id: "cat-1", slug: "payslip", icon: "Banknote", color: "#FF9500", parent_id: "parent-finance" },
      { id: "cat-2", slug: "invoice", icon: "Receipt", color: "#FF3B30", parent_id: "parent-finance" },
    ]);
    vi.mocked(api.listDocuments).mockResolvedValue([
      { ...docs[0], category_id: "cat-1" },
      { ...docs[1], category_id: "cat-2" },
    ]);
    renderPage();
    await screen.findByText("document-0.pdf");

    fireEvent.click(await screen.findByRole("button", { name: "Payslip & Salary" }));

    expect(screen.getByText("document-0.pdf")).toBeInTheDocument();
    expect(screen.queryByText("document-1.pdf")).not.toBeInTheDocument();
  });

  it("toggling a category group header filters to all its children at once", async () => {
    vi.mocked(api.listCategories).mockResolvedValue([
      { id: "parent-finance", slug: "finance", icon: "Coins", color: "#FF9500", parent_id: null },
      { id: "cat-1", slug: "payslip", icon: "Banknote", color: "#FF9500", parent_id: "parent-finance" },
      { id: "cat-2", slug: "invoice", icon: "Receipt", color: "#FF3B30", parent_id: "parent-finance" },
    ]);
    vi.mocked(api.listDocuments).mockResolvedValue([
      { ...docs[0], category_id: "cat-1" },
      { ...docs[1], category_id: "cat-2" },
      { ...docs[2], category_id: null },
    ]);
    renderPage();
    await screen.findByText("document-0.pdf");

    fireEvent.click(await screen.findByRole("button", { name: "Finance" }));

    expect(screen.getByText("document-0.pdf")).toBeInTheDocument();
    expect(screen.getByText("document-1.pdf")).toBeInTheDocument();
    expect(screen.queryByText("document-2.pdf")).not.toBeInTheDocument();
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

  it("clicking Export CSV downloads the documents CSV", async () => {
    vi.mocked(api.downloadDocumentsCsv).mockResolvedValue(undefined);
    renderPage();
    await screen.findByText("document-0.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    await waitFor(() => expect(api.downloadDocumentsCsv).toHaveBeenCalledTimes(1));
  });

  it("shows a toast if the CSV export fails", async () => {
    vi.mocked(api.downloadDocumentsCsv).mockRejectedValue(new Error("network error"));
    renderPage();
    await screen.findByText("document-0.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    expect(await screen.findByText(/export/i)).toBeInTheDocument();
  });

  it("does not show a workspace switcher when nothing is shared with me", async () => {
    renderPage();
    await screen.findByText("document-0.pdf");
    expect(screen.queryByLabelText("Viewing workspace")).not.toBeInTheDocument();
  });

  it("shows a workspace switcher and switches to a shared workspace's documents", async () => {
    vi.mocked(api.listWorkspacesSharedWithMe).mockResolvedValue([
      {
        id: "wm-1", owner_id: "owner-9", owner_username: "owner9", owner_display_name: "Owner Nine",
        member_id: "self", member_username: "self", member_display_name: "Self",
        can_export: false, status: "accepted", created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    const sharedDocs: api.DocumentOut[] = [
      { ...docs[0], id: "shared-doc-1", title: "shared-file.pdf" },
    ];
    vi.mocked(api.listDocuments).mockImplementation((ownerId?: string) =>
      Promise.resolve(ownerId === "owner-9" ? sharedDocs : docs)
    );

    renderPage();
    await screen.findByText("document-0.pdf");

    const switcher = await screen.findByLabelText("Viewing workspace");
    fireEvent.change(switcher, { target: { value: "owner-9" } });

    expect(await screen.findByText("shared-file.pdf")).toBeInTheDocument();
    expect(screen.queryByText("document-0.pdf")).not.toBeInTheDocument();
  });

  it("hides row-selection checkboxes and the upload button while viewing a shared workspace", async () => {
    vi.mocked(api.listWorkspacesSharedWithMe).mockResolvedValue([
      {
        id: "wm-1", owner_id: "owner-9", owner_username: "owner9", owner_display_name: "Owner Nine",
        member_id: "self", member_username: "self", member_display_name: "Self",
        can_export: false, status: "accepted", created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    renderPage();
    await screen.findByText("document-0.pdf");

    expect(screen.getAllByRole("checkbox").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Upload document" })).toBeInTheDocument();

    fireEvent.change(await screen.findByLabelText("Viewing workspace"), { target: { value: "owner-9" } });
    await waitFor(() => expect(screen.queryAllByRole("checkbox")).toHaveLength(0));
    expect(screen.queryByRole("button", { name: "Upload document" })).not.toBeInTheDocument();
  });

  it("hides the Export CSV button for a shared workspace without export permission", async () => {
    vi.mocked(api.listWorkspacesSharedWithMe).mockResolvedValue([
      {
        id: "wm-1", owner_id: "owner-9", owner_username: "owner9", owner_display_name: "Owner Nine",
        member_id: "self", member_username: "self", member_display_name: "Self",
        can_export: false, status: "accepted", created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    renderPage();
    await screen.findByText("document-0.pdf");
    fireEvent.change(await screen.findByLabelText("Viewing workspace"), { target: { value: "owner-9" } });
    await waitFor(() => expect(screen.queryByRole("button", { name: "Export CSV" })).not.toBeInTheDocument());
  });

  it("clicking a document row navigates to its detail route and opens the drawer with fetched document data", async () => {
    vi.mocked(api.getDocument).mockResolvedValue({ ...docs[1], ocr_text: null, chunk_count: 0, summary: null, correspondent_street: null, correspondent_house_number: null, correspondent_po_box: null, correspondent_postal_code: null, correspondent_city: null, correspondent_country: null, metafields: null });
    renderPage();
    fireEvent.click(await screen.findByRole("link", { name: "document-1.pdf" }));

    await waitFor(() => expect(api.getDocument).toHaveBeenCalledWith("doc-1"));
    expect(await screen.findByTestId("drawer-backdrop")).toBeInTheDocument();
  });

  it("deleting a document from the drawer calls deleteDocument and closes the drawer", async () => {
    vi.mocked(api.getDocument).mockResolvedValue({ ...docs[1], ocr_text: null, chunk_count: 0, summary: null, correspondent_street: null, correspondent_house_number: null, correspondent_po_box: null, correspondent_postal_code: null, correspondent_city: null, correspondent_country: null, metafields: null });
    vi.mocked(api.deleteDocument).mockResolvedValue(undefined);
    renderPage("/documents/doc-1");
    await screen.findByTestId("drawer-backdrop");

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete document" }));

    await waitFor(() => expect(api.deleteDocument).toHaveBeenCalledWith("doc-1"));
    await waitFor(() => expect(screen.queryByTestId("drawer-backdrop")).not.toBeInTheDocument());
  });
});
