import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import DocumentDetail from "./DocumentDetail";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getDocument: vi.fn(),
    deleteDocument: vi.fn(),
    summarizeDocument: vi.fn(),
  };
});

const mockDoc = {
  id: "doc-1",
  title: "factuur-77621.pdf",
  filename: "factuur-77621.pdf",
  mime_type: "application/pdf",
  status: "ready",
  error: null,
  created_at: "2026-07-08T19:11:38Z",
  processed_at: "2026-07-08T19:12:00Z",
  ocr_text: "Extracted text here",
  chunk_count: 3,
  summary: null,
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
});
