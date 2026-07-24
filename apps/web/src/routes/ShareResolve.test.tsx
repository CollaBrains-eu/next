import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import ShareResolve from "./ShareResolve";
import { ApiError } from "../lib/api";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, resolveShareLink: vi.fn(), listActivity: vi.fn() };
});

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin", role: "member" } }),
}));

function renderAt(token: string) {
  return render(
    <MemoryRouter initialEntries={[`/share/${token}`]}>
      <ToastProvider>
        <Routes>
          <Route path="/share/:token" element={<ShareResolve />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  );
}

describe("ShareResolve", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listActivity).mockResolvedValue([]);
  });

  it("resolves and renders a shared document", async () => {
    vi.mocked(api.resolveShareLink).mockResolvedValue({
      entity_type: "document",
      data: {
        id: "doc-1", title: "factuur.pdf", filename: "factuur.pdf", mime_type: "application/pdf",
        status: "ready", error: null, doc_type: null, tags: [], correspondent: null,
        created_at: "2026-01-01T00:00:00Z", processed_at: null, category_id: null,
        ocr_text: null, chunk_count: 0, summary: null, correspondent_street: null,
        correspondent_house_number: null, correspondent_po_box: null, correspondent_postal_code: null,
        correspondent_city: null, correspondent_country: null, metafields: null,
      },
    });
    renderAt("tok123");

    expect(await screen.findByText("Shared with you")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
  });

  it("resolves and renders a shared case", async () => {
    vi.mocked(api.resolveShareLink).mockResolvedValue({
      entity_type: "case",
      data: {
        id: "c1", name: "Alpha matter", description: null, status: "open", created_at: "2026-01-01T00:00:00Z",
        document_count: 0, member_count: 0, documents: [], tasks: [], decisions: [], vehicles: [],
        appointments: [], is_owner: true, owner_display_name: "Alice Owner",
      },
    });
    renderAt("tok456");

    expect(await screen.findByText("Owned by Alice Owner")).toBeInTheDocument();
  });

  it("resolves and renders a shared task", async () => {
    vi.mocked(api.resolveShareLink).mockResolvedValue({
      entity_type: "task",
      data: {
        id: "t1", document_id: null, title: "Chase invoice", description: null, due_date: null,
        assignee: null, status: "open", position: 0, source: "manual", created_at: "2026-01-01T00:00:00Z",
        recurrence_rule: null, category: null,
      },
    });
    renderAt("tok789");

    expect(await screen.findByText("Chase invoice")).toBeInTheDocument();
  });

  it("shows an error alert for an expired or unknown token", async () => {
    vi.mocked(api.resolveShareLink).mockRejectedValue(new ApiError(404, "Share link not found or expired"));
    renderAt("bad-token");

    expect(await screen.findByText("Share link not found or expired")).toBeInTheDocument();
  });
});
