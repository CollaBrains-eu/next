import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DocumentDetailContent } from "./DocumentDetailContent";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin", role: "admin" } }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
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

function renderContent(doc = mockDoc, onChanged = vi.fn()) {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <DocumentDetailContent document={doc} onChanged={onChanged} />
      </ToastProvider>
    </MemoryRouter>
  );
}

describe("DocumentDetailContent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a Ready badge", () => {
    renderContent();
    expect(screen.getByText("ready")).toBeInTheDocument();
  });

  it("shows extracted text in a card", () => {
    renderContent();
    expect(screen.getByText("Extracted text here")).toBeInTheDocument();
  });

  it("does not show a Classification card when nothing was classified", () => {
    renderContent();
    expect(screen.queryByText("Classification")).not.toBeInTheDocument();
  });

  it("shows doc type, tags, and correspondent with address once classified", () => {
    renderContent({
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

    expect(screen.getByText("Classification")).toBeInTheDocument();
    expect(screen.getByText("invoice")).toBeInTheDocument();
    expect(screen.getByText("btw")).toBeInTheDocument();
    expect(screen.getByText("q3")).toBeInTheDocument();
    expect(screen.getByText("SNS Bank N.V.")).toBeInTheDocument();
    expect(screen.getByText("Rembrandtlaan 1, 4700 BP Roosendaal, Netherlands")).toBeInTheDocument();
  });

  it("shows a Reprocess button for admins when a document failed", () => {
    renderContent({ ...mockDoc, status: "failed", error: "OCR timed out" });
    expect(screen.getByRole("button", { name: "Reprocess" })).toBeInTheDocument();
  });

  it("clicking Reprocess calls reprocessDocument and onChanged", async () => {
    vi.mocked(api.reprocessDocument).mockResolvedValue({ status: "reprocess_queued" });
    const onChanged = vi.fn();
    renderContent({ ...mockDoc, status: "failed", error: "OCR timed out" }, onChanged);

    fireEvent.click(screen.getByRole("button", { name: "Reprocess" }));
    await waitFor(() => expect(api.reprocessDocument).toHaveBeenCalledWith("doc-1"));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it("does not show a Reprocess button for ready documents", () => {
    renderContent();
    expect(screen.queryByRole("button", { name: "Reprocess" })).not.toBeInTheDocument();
  });

  it("shows Preview and Download buttons for a ready PDF document", () => {
    renderContent();
    expect(screen.getByRole("button", { name: "Preview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  });

  it("does not show a Preview button for a non-previewable mime type", () => {
    renderContent({ ...mockDoc, mime_type: "text/plain" });
    expect(screen.queryByRole("button", { name: "Preview" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  });

  it("clicking Download calls downloadDocumentFile with the document id and filename", async () => {
    vi.mocked(api.downloadDocumentFile).mockResolvedValue(undefined);
    renderContent();
    fireEvent.click(screen.getByRole("button", { name: "Download" }));
    await waitFor(() => expect(api.downloadDocumentFile).toHaveBeenCalledWith("doc-1", "factuur-77621.pdf"));
  });

  it("clicking Preview calls previewDocumentFile with the document id", async () => {
    vi.mocked(api.previewDocumentFile).mockResolvedValue(undefined);
    renderContent();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(api.previewDocumentFile).toHaveBeenCalledWith("doc-1"));
  });

  it("renders the metafields card when metafields are present", () => {
    renderContent({
      ...mockDoc, doc_type: "invoice",
      metafields: { amount: "500.00", due_date: "2026-08-15", invoice_number: "INV-123" },
    });

    expect(screen.getByText("Invoice Number")).toBeInTheDocument();
    expect(screen.getByText("INV-123")).toBeInTheDocument();
  });

  it("does not render the metafields card when metafields are absent", () => {
    renderContent();
    expect(screen.queryByText("Invoice Number")).not.toBeInTheDocument();
  });

  it("shows an add-to-calendar button for date-like metafields and downloads on click", async () => {
    vi.mocked(api.downloadMetafieldIcs).mockResolvedValue(undefined);
    renderContent({
      ...mockDoc, doc_type: "invoice",
      metafields: { amount: "500.00", due_date: "2026-08-15" },
    });

    fireEvent.click(screen.getByRole("button", { name: /add to calendar/i }));

    await waitFor(() =>
      expect(api.downloadMetafieldIcs).toHaveBeenCalledWith("doc-1", "due_date", expect.stringContaining("due-date"))
    );
  });
});
