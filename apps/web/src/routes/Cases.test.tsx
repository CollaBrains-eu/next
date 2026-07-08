import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Cases from "./Cases";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listCases: vi.fn(),
    createCase: vi.fn(),
  };
});

const CASES: api.CaseOut[] = [
  { id: "c1", name: "Alpha matter", description: "First case", status: "open", created_at: "2026-01-01T00:00:00Z" },
  { id: "c2", name: "Beta matter", description: null, status: "closed", created_at: "2026-01-02T00:00:00Z" },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <Cases />
    </MemoryRouter>
  );
}

describe("Cases", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listCases).mockResolvedValue(CASES);
    vi.mocked(api.createCase).mockResolvedValue(CASES[0]);
  });

  it("renders case cards with name and status badge", async () => {
    renderPage();
    expect(await screen.findByText("Alpha matter")).toBeInTheDocument();
    expect(screen.getByText("Beta matter")).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();
    expect(screen.getByText("closed")).toBeInTheDocument();
  });

  it("shows EmptyState when there are no cases", async () => {
    vi.mocked(api.listCases).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No cases yet.")).toBeInTheDocument();
  });

  it("reveals the create form when New case is clicked", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByRole("button", { name: "New case" }));
    expect(screen.getByPlaceholderText("Case name")).toBeInTheDocument();
  });

  it("submits the form and calls createCase", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByRole("button", { name: "New case" }));
    fireEvent.change(screen.getByPlaceholderText("Case name"), { target: { value: "Gamma matter" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(api.createCase).toHaveBeenCalledWith("Gamma matter", undefined));
  });

  it("shows an error banner when loading fails", async () => {
    vi.mocked(api.listCases).mockRejectedValue(new api.ApiError(500, "Boom"));
    renderPage();
    expect(await screen.findByText("Boom")).toBeInTheDocument();
  });
});
