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
    listMyCaseInvitations: vi.fn(),
    acceptCaseInvitation: vi.fn(),
    declineCaseInvitation: vi.fn(),
  };
});

const CASES: api.CaseOut[] = [
  { id: "c1", name: "Alpha matter", description: "First case", status: "open", created_at: "2026-01-01T00:00:00Z" },
  { id: "c2", name: "Beta matter", description: null, status: "closed", created_at: "2026-01-02T00:00:00Z" },
];

const INVITATION: api.CaseMemberOut = {
  id: "m1", case_id: "c3", case_name: "Gamma matter", user_id: "u1",
  username: "me", user_display_name: "Me", role: "member", status: "pending", created_at: "2026-01-01T00:00:00Z",
};

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
    vi.mocked(api.listMyCaseInvitations).mockResolvedValue([]);
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
});
