import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import DocumentDetail from "./DocumentDetail";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin", role: "admin" } }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getDocument: vi.fn(),
    deleteDocument: vi.fn(),
    summarizeDocument: vi.fn(),
    reprocessDocument: vi.fn(),
    downloadDocumentFile: vi.fn(),
    previewDocumentFile: vi.fn(),
    downloadMetafieldIcs: vi.fn(),
  };
});

const mockDoc = {
  id: "doc-1",
  title: "factuur-77621.pdf",
  filename: "factuur-77621.pdf",
  mime_type: "application/pdf",
  status: "ready",
  error: null,
  doc_type: null,
  tags: [],
  correspondent: null,
  created_at: "2026-07-08T19:11:38Z",
  processed_at: "2026-07-08T19:12:00Z",
  category_id: null,
  ocr_text: "Extracted text here",
  chunk_count: 3,
  summary: null,
  correspondent_street: null,
  correspondent_house_number: null,
  correspondent_po_box: null,
  correspondent_postal_code: null,
  correspondent_city: null,
  correspondent_country: null,
  metafields: null,
};

function renderAt(id: string) {
  return render(
    <MemoryRouter initialEntries={[`/documents/${id}`]}>
      <ToastProvider>
        <Routes>
          <Route path="/documents/:id" element={<DocumentDetail />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  );
}

describe("DocumentDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getDocument).mockResolvedValue(mockDoc);
  });

  it("shows the document title and a Ready badge once loaded", async () => {
    renderAt("doc-1");
    expect(await screen.findByRole("heading", { name: "factuur-77621.pdf" })).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
  });

  it("shows extracted text in a card", async () => {
    renderAt("doc-1");
    expect(await screen.findByText("Extracted text here")).toBeInTheDocument();
  });

  it("does not show a Classification card when nothing was classified", async () => {
    renderAt("doc-1");
    await screen.findByRole("heading", { name: "factuur-77621.pdf" });
    expect(screen.queryByText("Classification")).not.toBeInTheDocument();
  });

  it("shows doc type, tags, and correspondent with address once classified", async () => {
    vi.mocked(api.getDocument).mockResolvedValue({
      ...mockDoc,
      doc_type: "invoice",
      tags: ["btw", "q3"],
      correspondent: "SNS Bank N.V.",
      correspondent_street: "Rembrandtlaan",
      correspondent_house_number: "1",
      correspondent_po_box: null,
      correspondent_postal_code: "4700 BP",
      correspondent_city: "Roosendaal",
      correspondent_country: "Netherlands",
    });
    renderAt("doc-1");

    expect(await screen.findByText("Classification")).toBeInTheDocument();
    expect(screen.getByText("invoice")).toBeInTheDocument();
    expect(screen.getByText("btw")).toBeInTheDocument();
    expect(screen.getByText("q3")).toBeInTheDocument();
    expect(screen.getByText("SNS Bank N.V.")).toBeInTheDocument();
    expect(screen.getByText("Rembrandtlaan 1, 4700 BP Roosendaal, Netherlands")).toBeInTheDocument();
  });

  it("shows correspondent name without an address line when no address was found", async () => {
    vi.mocked(api.getDocument).mockResolvedValue({ ...mockDoc, correspondent: "Anonymous Sender" });
    renderAt("doc-1");

    expect(await screen.findByText("Anonymous Sender")).toBeInTheDocument();
  });

  it("clicking Delete opens a confirmation Modal, not window.confirm", async () => {
    renderAt("doc-1");
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument();
  });

  it("confirming the modal calls deleteDocument and shows a toast", async () => {
    vi.mocked(api.deleteDocument).mockResolvedValue(undefined);
    renderAt("doc-1");
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete document" }));
    await waitFor(() => expect(api.deleteDocument).toHaveBeenCalledWith("doc-1"));
    expect(await screen.findByText(/deleted/i)).toBeInTheDocument();
  });

  it("canceling the modal does not call deleteDocument", async () => {
    renderAt("doc-1");
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(api.deleteDocument).not.toHaveBeenCalled();
  });

  it("shows a Reprocess button for admins when a document failed", async () => {
    vi.mocked(api.getDocument).mockResolvedValue({ ...mockDoc, status: "failed", error: "OCR timed out" });
    renderAt("doc-1");
    expect(await screen.findByRole("button", { name: "Reprocess" })).toBeInTheDocument();
  });

  it("clicking Reprocess calls reprocessDocument and shows a toast", async () => {
    vi.mocked(api.getDocument).mockResolvedValue({ ...mockDoc, status: "failed", error: "OCR timed out" });
    vi.mocked(api.reprocessDocument).mockResolvedValue({ status: "reprocess_queued" });
    renderAt("doc-1");
    fireEvent.click(await screen.findByRole("button", { name: "Reprocess" }));
    await waitFor(() => expect(api.reprocessDocument).toHaveBeenCalledWith("doc-1"));
    expect(await screen.findByText(/reprocessing started/i)).toBeInTheDocument();
  });

  it("does not show a Reprocess button for ready documents", async () => {
    renderAt("doc-1");
    await screen.findByRole("heading", { name: "factuur-77621.pdf" });
    expect(screen.queryByRole("button", { name: "Reprocess" })).not.toBeInTheDocument();
  });

  it("shows Preview and Download buttons for a ready PDF document", async () => {
    renderAt("doc-1");
    expect(await screen.findByRole("button", { name: "Preview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  });

  it("does not show a Preview button for a non-previewable mime type", async () => {
    vi.mocked(api.getDocument).mockResolvedValue({ ...mockDoc, mime_type: "text/plain" });
    renderAt("doc-1");
    await screen.findByRole("heading", { name: "factuur-77621.pdf" });
    expect(screen.queryByRole("button", { name: "Preview" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  });

  it("clicking Download calls downloadDocumentFile with the document id and filename", async () => {
    vi.mocked(api.downloadDocumentFile).mockResolvedValue(undefined);
    renderAt("doc-1");
    fireEvent.click(await screen.findByRole("button", { name: "Download" }));
    await waitFor(() => expect(api.downloadDocumentFile).toHaveBeenCalledWith("doc-1", "factuur-77621.pdf"));
  });

  it("clicking Preview calls previewDocumentFile with the document id", async () => {
    vi.mocked(api.previewDocumentFile).mockResolvedValue(undefined);
    renderAt("doc-1");
    fireEvent.click(await screen.findByRole("button", { name: "Preview" }));
    await waitFor(() => expect(api.previewDocumentFile).toHaveBeenCalledWith("doc-1"));
  });

  it("renders the metafields card when metafields are present", async () => {
    vi.mocked(api.getDocument).mockResolvedValue({
      ...mockDoc, doc_type: "invoice",
      metafields: { amount: "500.00", due_date: "2026-08-15", invoice_number: "INV-123" },
    });
    renderAt("doc-1");

    expect(await screen.findByText("Invoice Number")).toBeInTheDocument();
    expect(screen.getByText("INV-123")).toBeInTheDocument();
  });

  it("does not render the metafields card when metafields are absent", async () => {
    vi.mocked(api.getDocument).mockResolvedValue(mockDoc);
    renderAt("doc-1");

    await screen.findByRole("heading", { name: mockDoc.title });
    expect(screen.queryByText("Invoice Number")).not.toBeInTheDocument();
  });

  it("shows an add-to-calendar button for date-like metafields and downloads on click", async () => {
    vi.mocked(api.getDocument).mockResolvedValue({
      ...mockDoc, doc_type: "invoice",
      metafields: { amount: "500.00", due_date: "2026-08-15" },
    });
    vi.mocked(api.downloadMetafieldIcs).mockResolvedValue(undefined);
    renderAt("doc-1");

    const button = await screen.findByRole("button", { name: /add to calendar/i });
    fireEvent.click(button);

    await waitFor(() =>
      expect(api.downloadMetafieldIcs).toHaveBeenCalledWith("doc-1", "due_date", expect.stringContaining("due-date"))
    );
  });
});
