import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard, { getGreetingKey } from "./Dashboard";
import * as api from "../lib/api";

const { mockUseAuth } = vi.hoisted(() => ({ mockUseAuth: vi.fn() }));
vi.mock("../lib/auth", () => ({ useAuth: mockUseAuth }));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listDocuments: vi.fn(),
    listTasks: vi.fn(),
    listCases: vi.fn(),
    listEntities: vi.fn(),
    getAdminHealth: vi.fn(),
  };
});

function renderPage() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({ user: { display_name: "Ada Lovelace", role: "member" } });
    vi.mocked(api.listDocuments).mockResolvedValue([]);
    vi.mocked(api.listTasks).mockResolvedValue([]);
    vi.mocked(api.listCases).mockResolvedValue([]);
    vi.mocked(api.listEntities).mockResolvedValue([]);
    vi.mocked(api.getAdminHealth).mockResolvedValue([]);
  });

  it("greets the signed-in user by name in the page heading", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Ada Lovelace");
  });

  it("renders the AI quick action links", async () => {
    renderPage();
    expect(await screen.findByRole("link", { name: /Ask a question/ })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: /Draft a document/ })).toHaveAttribute("href", "/legal");
    expect(screen.getByRole("link", { name: /Ask the assistant/ })).toHaveAttribute("href", "/assistant");
    expect(screen.getByRole("link", { name: /View tasks/ })).toHaveAttribute("href", "/tasks");
  });

  it("shows the most recent documents, newest first", async () => {
    vi.mocked(api.listDocuments).mockResolvedValue([
      { id: "d1", title: "Older lease", filename: "a.pdf", mime_type: "application/pdf", status: "ready", error: null, created_at: "2026-01-01T00:00:00Z", processed_at: null, category_id: null },
      { id: "d2", title: "Newer invoice", filename: "b.pdf", mime_type: "application/pdf", status: "ready", error: null, created_at: "2026-02-01T00:00:00Z", processed_at: null, category_id: null },
    ]);
    renderPage();
    const links = await screen.findAllByRole("link", { name: /Older lease|Newer invoice/ });
    expect(links[0]).toHaveTextContent("Newer invoice");
    expect(links[1]).toHaveTextContent("Older lease");
  });

  it("shows the recent-documents empty state when there are none", async () => {
    renderPage();
    expect(await screen.findByText("No documents yet.")).toBeInTheDocument();
  });

  it("shows open tasks", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      { id: "t1", document_id: null, title: "Review lease", description: null, due_date: null, assignee: null, status: "open", position: 0, source: "manual", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("Review lease")).toBeInTheDocument();
    expect(api.listTasks).toHaveBeenCalledWith("open");
  });

  it("shows the pending entity review count linking to the review queue", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([
      { id: "e1", name: "Acme BV", entity_type: "organization", status: "pending_review", created_at: "2026-01-01T00:00:00Z" },
      { id: "e2", name: "Jane Doe", entity_type: "person", status: "pending_review", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("2 entities waiting for review")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "2 entities waiting for review" })).toHaveAttribute("href", "/entities/review");
  });

  it("shows recent cases", async () => {
    vi.mocked(api.listCases).mockResolvedValue([
      { id: "c1", name: "Smith matter", description: null, status: "open", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("Smith matter")).toBeInTheDocument();
  });

  it("shows a system status widget for admins", async () => {
    mockUseAuth.mockReturnValue({ user: { display_name: "Ada Admin", role: "admin" } });
    vi.mocked(api.getAdminHealth).mockResolvedValue([{ name: "postgres", status: "up", detail: null }]);
    renderPage();
    expect(await screen.findByText("System status")).toBeInTheDocument();
    expect(await screen.findByText("postgres")).toBeInTheDocument();
  });

  it("hides the system status widget for non-admins", async () => {
    renderPage();
    await waitFor(() => expect(api.listDocuments).toHaveBeenCalled());
    expect(screen.queryByText("System status")).not.toBeInTheDocument();
    expect(api.getAdminHealth).not.toHaveBeenCalled();
  });
});

describe("getGreetingKey", () => {
  it("returns the morning key before noon", () => {
    expect(getGreetingKey(0)).toBe("dashboard.greetingMorning");
    expect(getGreetingKey(11)).toBe("dashboard.greetingMorning");
  });

  it("returns the afternoon key from noon up to 6pm", () => {
    expect(getGreetingKey(12)).toBe("dashboard.greetingAfternoon");
    expect(getGreetingKey(17)).toBe("dashboard.greetingAfternoon");
  });

  it("returns the evening key from 6pm onward", () => {
    expect(getGreetingKey(18)).toBe("dashboard.greetingEvening");
    expect(getGreetingKey(23)).toBe("dashboard.greetingEvening");
  });
});
