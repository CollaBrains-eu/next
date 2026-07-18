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
    downloadCasesCsv: vi.fn(),
    updateCaseStatus: vi.fn(),
  };
});

const CASES: api.CaseOut[] = [
  {
    id: "c1", name: "Alpha matter", description: "First case", status: "open",
    created_at: "2026-01-01T00:00:00Z", document_count: 3, member_count: 1,
  },
  {
    id: "c2", name: "Beta matter", description: null, status: "closed",
    created_at: "2026-01-02T00:00:00Z", document_count: 0, member_count: 0,
  },
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
    vi.mocked(api.updateCaseStatus).mockImplementation(async (id, status) => ({
      ...CASES.find((c) => c.id === id)!,
      status,
    }));
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
    expect(await screen.findByText("No cases yet")).toBeInTheDocument();
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

  it("clicking Export CSV downloads the cases CSV", async () => {
    vi.mocked(api.downloadCasesCsv).mockResolvedValue(undefined);
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    await waitFor(() => expect(api.downloadCasesCsv).toHaveBeenCalledTimes(1));
  });

  it("shows an error banner if the CSV export fails", async () => {
    vi.mocked(api.downloadCasesCsv).mockRejectedValue(new api.ApiError(500, "Export broke"));
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    expect(await screen.findByText("Export broke")).toBeInTheDocument();
  });

  it("filters by name/description as you type", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "beta" } });
    expect(screen.queryByText("Alpha matter")).not.toBeInTheDocument();
    expect(screen.getByText("Beta matter")).toBeInTheDocument();
  });

  it("filters by status via FilterChips", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByText("+ Add filter"));
    fireEvent.click(screen.getByText("Open"));
    expect(screen.getByText("Alpha matter")).toBeInTheDocument();
    expect(screen.queryByText("Beta matter")).not.toBeInTheDocument();
  });

  it("switches to table view and shows document/member counts", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByRole("button", { name: "Table" }));
    const row = screen.getByText("Alpha matter").closest("tr")!;
    expect(row).toHaveTextContent("3");
    expect(row).toHaveTextContent("1");
  });

  it("bulk-closes selected open cases and refetches", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByRole("button", { name: "Table" }));
    const row = screen.getByText("Alpha matter").closest("tr")!;
    fireEvent.click(row.querySelector("input[type=checkbox]")!);
    fireEvent.click(screen.getByRole("button", { name: "Close selected" }));
    await waitFor(() => expect(api.updateCaseStatus).toHaveBeenCalledWith("c1", "closed"));
  });

  it("bulk-close is a no-op for rows already closed", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByRole("button", { name: "Table" }));
    const row = screen.getByText("Beta matter").closest("tr")!;
    fireEvent.click(row.querySelector("input[type=checkbox]")!);
    fireEvent.click(screen.getByRole("button", { name: "Close selected" }));
    await waitFor(() => expect(screen.queryByText("1 selected")).not.toBeInTheDocument());
    expect(api.updateCaseStatus).not.toHaveBeenCalled();
  });
});
