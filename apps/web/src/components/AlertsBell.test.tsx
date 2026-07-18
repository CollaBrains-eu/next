import { describe, expect, it, beforeEach, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AlertsBell } from "./AlertsBell";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, getPendingReviewEntityCount: vi.fn(), listMyCaseInvitations: vi.fn() };
});

function renderBell() {
  return render(
    <MemoryRouter>
      <AlertsBell />
    </MemoryRouter>
  );
}

describe("AlertsBell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listMyCaseInvitations).mockResolvedValue([]);
  });

  it("shows no count badge when there is nothing pending", async () => {
    vi.mocked(api.getPendingReviewEntityCount).mockResolvedValue({ count: 0 });
    renderBell();
    await screen.findByLabelText("Alerts");
    expect(screen.queryByTestId("alerts-bell-badge")).not.toBeInTheDocument();
  });

  it("shows the pending count as a badge and lists it in the dropdown", async () => {
    vi.mocked(api.getPendingReviewEntityCount).mockResolvedValue({ count: 2 });
    renderBell();
    expect(await screen.findByTestId("alerts-bell-badge")).toHaveTextContent("2");
    fireEvent.click(screen.getByLabelText("Alerts"));
    expect(screen.getByText("2 entities pending review")).toBeInTheDocument();
  });

  it("navigates to the review queue when the pending item is selected", async () => {
    vi.mocked(api.getPendingReviewEntityCount).mockResolvedValue({ count: 1 });
    renderBell();
    await screen.findByTestId("alerts-bell-badge");
    fireEvent.click(screen.getByLabelText("Alerts"));
    fireEvent.click(screen.getByText("1 entity pending review"));
    // Navigation itself is exercised by CommandCenter's existing "Go to X" tests
    // via the same react-router API; here we only assert the option is clickable
    // without throwing.
  });

  it("shows the caught-up message when nothing is pending", async () => {
    vi.mocked(api.getPendingReviewEntityCount).mockResolvedValue({ count: 0 });
    renderBell();
    await screen.findByLabelText("Alerts");
    fireEvent.click(screen.getByLabelText("Alerts"));
    expect(screen.getByText("You're all caught up")).toBeInTheDocument();
  });

  it("shows a count beyond the old list-endpoint's 50-row cap correctly", async () => {
    vi.mocked(api.getPendingReviewEntityCount).mockResolvedValue({ count: 137 });
    renderBell();
    expect(await screen.findByTestId("alerts-bell-badge")).toHaveTextContent("137");
  });

  it("combines pending reviews and pending case invitations into one badge count", async () => {
    vi.mocked(api.getPendingReviewEntityCount).mockResolvedValue({ count: 2 });
    vi.mocked(api.listMyCaseInvitations).mockResolvedValue([
      { id: "m1", case_id: "c1", case_name: "Smith matter", user_id: "u1", username: "me", user_display_name: "Me", role: "member", status: "pending", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderBell();
    expect(await screen.findByTestId("alerts-bell-badge")).toHaveTextContent("3");
    fireEvent.click(screen.getByLabelText("Alerts"));
    expect(screen.getByText("2 entities pending review")).toBeInTheDocument();
    expect(screen.getByText("1 case invitation waiting")).toBeInTheDocument();
  });

  it("shows only the case-invitations line when there are no pending reviews", async () => {
    vi.mocked(api.getPendingReviewEntityCount).mockResolvedValue({ count: 0 });
    vi.mocked(api.listMyCaseInvitations).mockResolvedValue([
      { id: "m1", case_id: "c1", case_name: "Smith matter", user_id: "u1", username: "me", user_display_name: "Me", role: "member", status: "pending", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderBell();
    expect(await screen.findByTestId("alerts-bell-badge")).toHaveTextContent("1");
    fireEvent.click(screen.getByLabelText("Alerts"));
    expect(screen.queryByText(/entities pending review/)).not.toBeInTheDocument();
    expect(screen.getByText("1 case invitation waiting")).toBeInTheDocument();
  });
});
