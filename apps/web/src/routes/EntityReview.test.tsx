import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EntityReview from "./EntityReview";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listEntities: vi.fn(),
    approveEntity: vi.fn(),
    rejectEntity: vi.fn(),
    bulkReviewEntities: vi.fn(),
  };
});

const PENDING: api.EntityOut[] = [
  { id: "p1", name: "Nadia Petrov", entity_type: "person", status: "pending_review", created_at: "2026-01-01T00:00:00Z", maps_url: null },
  { id: "p2", name: "Fenwick LLC", entity_type: "organization", status: "pending_review", created_at: "2026-01-02T00:00:00Z", maps_url: null },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <EntityReview />
    </MemoryRouter>
  );
}

describe("EntityReview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listEntities).mockResolvedValue(PENDING);
  });

  it("shows the first pending entity with a counter", async () => {
    renderPage();
    expect(await screen.findByText("Nadia Petrov")).toBeInTheDocument();
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
  });

  it("approving advances to the next card", async () => {
    vi.mocked(api.approveEntity).mockResolvedValue({ ...PENDING[0], status: "confirmed" });
    renderPage();
    await screen.findByText("Nadia Petrov");
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(api.approveEntity).toHaveBeenCalledWith("p1"));
    expect(await screen.findByText("Fenwick LLC")).toBeInTheDocument();
  });

  it("rejecting advances to the next card", async () => {
    vi.mocked(api.rejectEntity).mockResolvedValue({ ...PENDING[0], status: "rejected" });
    renderPage();
    await screen.findByText("Nadia Petrov");
    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    await waitFor(() => expect(api.rejectEntity).toHaveBeenCalledWith("p1"));
    expect(await screen.findByText("Fenwick LLC")).toBeInTheDocument();
  });

  it("J approves via keyboard, K rejects via keyboard", async () => {
    vi.mocked(api.approveEntity).mockResolvedValue({ ...PENDING[0], status: "confirmed" });
    renderPage();
    await screen.findByText("Nadia Petrov");
    fireEvent.keyDown(window, { key: "j" });
    await waitFor(() => expect(api.approveEntity).toHaveBeenCalledWith("p1"));
  });

  it("shows an empty state once the queue is cleared", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("Nothing to review")).toBeInTheDocument();
  });

  it("bulk-approve clears the whole queue", async () => {
    vi.mocked(api.bulkReviewEntities).mockResolvedValue(PENDING.map((e) => ({ ...e, status: "confirmed" })));
    renderPage();
    await screen.findByText("Nadia Petrov");
    fireEvent.click(screen.getByRole("button", { name: /approve all/i }));
    await waitFor(() =>
      expect(api.bulkReviewEntities).toHaveBeenCalledWith([
        { entity_id: "p1", action: "approve" },
        { entity_id: "p2", action: "approve" },
      ])
    );
    expect(await screen.findByText("Nothing to review")).toBeInTheDocument();
  });

  it("approve all only submits entities not already individually reviewed", async () => {
    vi.mocked(api.approveEntity).mockResolvedValue({ ...PENDING[0], status: "confirmed" });
    vi.mocked(api.bulkReviewEntities).mockResolvedValue([{ ...PENDING[1], status: "confirmed" }]);
    renderPage();
    await screen.findByText("Nadia Petrov");
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(api.approveEntity).toHaveBeenCalledWith("p1"));
    await screen.findByText("Fenwick LLC");

    fireEvent.click(screen.getByRole("button", { name: /approve all/i }));
    await waitFor(() =>
      expect(api.bulkReviewEntities).toHaveBeenCalledWith([{ entity_id: "p2", action: "approve" }])
    );
  });
});
