import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Cases from "./Cases";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listCases: vi.fn(),
    createCase: vi.fn(),
    downloadCasesCsv: vi.fn(),
    updateCaseStatus: vi.fn(),
    listMyCaseInvitations: vi.fn(),
    acceptCaseInvitation: vi.fn(),
    declineCaseInvitation: vi.fn(),
    getCase: vi.fn(),
    deleteCase: vi.fn(),
    listDocuments: vi.fn(),
    listTasks: vi.fn(),
    listDecisions: vi.fn(),
    listVehicles: vi.fn(),
    listCaseMembers: vi.fn(),
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

const INVITATION: api.CaseMemberOut = {
  id: "m1", case_id: "c3", case_name: "Gamma matter", user_id: "u1",
  username: "me", user_display_name: "Me", role: "member", status: "pending", created_at: "2026-01-01T00:00:00Z",
};

function renderPage(initialPath = "/cases") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ToastProvider>
        <Routes>
          <Route path="/cases" element={<Cases />} />
          <Route path="/cases/:id" element={<Cases />} />
        </Routes>
      </ToastProvider>
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
    vi.mocked(api.listMyCaseInvitations).mockResolvedValue([]);
    vi.mocked(api.listDocuments).mockResolvedValue([]);
    vi.mocked(api.listTasks).mockResolvedValue([]);
    vi.mocked(api.listDecisions).mockResolvedValue([]);
    vi.mocked(api.listVehicles).mockResolvedValue([]);
    vi.mocked(api.listCaseMembers).mockResolvedValue([]);
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

  it("shows a pending-invitations banner and accepts an invitation", async () => {
    vi.mocked(api.listMyCaseInvitations).mockResolvedValue([INVITATION]);
    vi.mocked(api.acceptCaseInvitation).mockResolvedValue({ ...INVITATION, status: "accepted" });
    renderPage();
    expect(await screen.findByText("Gamma matter")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(api.acceptCaseInvitation).toHaveBeenCalledWith("c3", "u1"));
    await waitFor(() => expect(screen.queryByText("Gamma matter")).not.toBeInTheDocument());
  });

  it("declines an invitation and removes it from the banner", async () => {
    vi.mocked(api.listMyCaseInvitations).mockResolvedValue([INVITATION]);
    vi.mocked(api.declineCaseInvitation).mockResolvedValue({ ...INVITATION, status: "declined" });
    renderPage();
    expect(await screen.findByText("Gamma matter")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Decline" }));
    await waitFor(() => expect(api.declineCaseInvitation).toHaveBeenCalledWith("c3", "u1"));
    await waitFor(() => expect(screen.queryByText("Gamma matter")).not.toBeInTheDocument());
  });

  it("does not show the pending-invitations banner when there are none", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    expect(screen.queryByText("Pending invitations")).not.toBeInTheDocument();
  });

  it("clicking a case card navigates to its detail route and opens the drawer with fetched case data", async () => {
    vi.mocked(api.getCase).mockResolvedValue({
      id: "c1", name: "Alpha matter", description: "First case", status: "open",
      created_at: "2026-01-01T00:00:00Z", document_count: 3, member_count: 1,
      documents: [], tasks: [], decisions: [], vehicles: [], appointments: [],
      is_owner: true, owner_display_name: "Alice Owner",
    });
    renderPage();
    fireEvent.click(await screen.findByRole("link", { name: /Alpha matter/ }));

    await waitFor(() => expect(api.getCase).toHaveBeenCalledWith("c1"));
    expect(await screen.findByTestId("drawer-backdrop")).toBeInTheDocument();
    expect(screen.getByText("Owned by Alice Owner")).toBeInTheDocument();
  });

  it("deleting a case from the drawer calls deleteCase and closes the drawer", async () => {
    vi.mocked(api.getCase).mockResolvedValue({
      id: "c1", name: "Alpha matter", description: null, status: "open",
      created_at: "2026-01-01T00:00:00Z", document_count: 0, member_count: 0,
      documents: [], tasks: [], decisions: [], vehicles: [], appointments: [],
      is_owner: true, owner_display_name: "Alice Owner",
    });
    vi.mocked(api.deleteCase).mockResolvedValue(undefined);
    renderPage("/cases/c1");
    await screen.findByTestId("drawer-backdrop");

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete case" }));

    await waitFor(() => expect(api.deleteCase).toHaveBeenCalledWith("c1"));
    await waitFor(() => expect(screen.queryByTestId("drawer-backdrop")).not.toBeInTheDocument());
  });
});
