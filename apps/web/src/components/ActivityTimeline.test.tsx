import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { ActivityTimeline } from "./ActivityTimeline";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, listDashboardActivity: vi.fn() };
});

function renderWidget() {
  return render(
    <MemoryRouter>
      <ActivityTimeline />
    </MemoryRouter>
  );
}

describe("ActivityTimeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders each activity item as a link with its title", async () => {
    vi.mocked(api.listDashboardActivity).mockResolvedValue([
      { type: "document", id: "d1", title: "Invoice Q3", created_at: "2026-07-22T10:00:00Z", link: "/documents/d1" },
      { type: "case", id: "c1", title: "Verhuizing Jansen", created_at: "2026-07-21T10:00:00Z", link: "/cases/c1" },
    ]);
    renderWidget();
    expect(await screen.findByRole("link", { name: /Invoice Q3/ })).toHaveAttribute("href", "/documents/d1");
    expect(screen.getByRole("link", { name: /Verhuizing Jansen/ })).toHaveAttribute("href", "/cases/c1");
  });

  it("shows the empty message when there is no activity", async () => {
    vi.mocked(api.listDashboardActivity).mockResolvedValue([]);
    renderWidget();
    expect(await screen.findByText("No recent activity.")).toBeInTheDocument();
  });
});
