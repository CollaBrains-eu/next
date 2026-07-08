import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Workspace from "./Workspace";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listDocuments: vi.fn(),
    search: vi.fn(),
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
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <Workspace />
    </MemoryRouter>
  );
}

describe("Workspace (Documents list)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listDocuments).mockResolvedValue(docs);
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
});
