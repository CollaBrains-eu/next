import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AddressHistory } from "./AddressHistory";
import { ApiError } from "../lib/api";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listMyResidencies: vi.fn(),
    listUserResidencies: vi.fn(),
    approveResidency: vi.fn(),
    rejectResidency: vi.fn(),
    correctResidency: vi.fn(),
  };
});

const RESIDENCY: api.ResidencyOut = {
  id: "res-1",
  address: {
    id: "addr-1", name: "Kerkstraat 12, Amsterdam", street: "Kerkstraat", house_number: "12",
    postal_code: "1012AB", city: "Amsterdam", country: "NL",
    maps_url: "https://www.google.com/maps/search/?api=1&query=Kerkstraat%2012%2C%201012AB%2C%20Amsterdam%2C%20NL",
  },
  valid_from: "2026-01-01",
  valid_to: null,
  status: "pending_review",
  source_document_id: "doc-1",
  linked_document_count: 1,
  created_at: "2026-01-01T00:00:00Z",
};

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("AddressHistory", () => {
  beforeEach(() => {
    vi.mocked(api.listMyResidencies).mockReset();
    vi.mocked(api.listUserResidencies).mockReset();
    vi.mocked(api.approveResidency).mockReset();
    vi.mocked(api.rejectResidency).mockReset();
    vi.mocked(api.correctResidency).mockReset();
  });

  it("shows an empty state when there is no history", async () => {
    vi.mocked(api.listMyResidencies).mockResolvedValue([]);
    renderWithRouter(<AddressHistory />);
    expect(await screen.findByText(/No address history yet/)).toBeInTheDocument();
  });

  it("renders a residency with its status and linked document count", async () => {
    vi.mocked(api.listMyResidencies).mockResolvedValue([RESIDENCY]);
    renderWithRouter(<AddressHistory />);
    expect(await screen.findByText("Kerkstraat 12, 1012AB Amsterdam")).toBeInTheDocument();
    expect(screen.getByText("Needs review")).toBeInTheDocument();
    expect(screen.getByText(/1 linked contract/)).toBeInTheDocument();
  });

  it("shows an error message when loading fails", async () => {
    vi.mocked(api.listMyResidencies).mockRejectedValue(new ApiError(500, "boom"));
    renderWithRouter(<AddressHistory />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });

  it("approves a pending residency", async () => {
    vi.mocked(api.listMyResidencies).mockResolvedValue([RESIDENCY]);
    vi.mocked(api.approveResidency).mockResolvedValue({ ...RESIDENCY, status: "confirmed" });
    renderWithRouter(<AddressHistory />);

    fireEvent.click(await screen.findByRole("button", { name: "Confirm" }));

    await waitFor(() => expect(api.approveResidency).toHaveBeenCalledWith("res-1"));
    await waitFor(() => expect(api.listMyResidencies).toHaveBeenCalledTimes(2));
  });

  it("rejects a pending residency", async () => {
    vi.mocked(api.listMyResidencies).mockResolvedValue([RESIDENCY]);
    vi.mocked(api.rejectResidency).mockResolvedValue({ ...RESIDENCY, status: "rejected" });
    renderWithRouter(<AddressHistory />);

    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));

    await waitFor(() => expect(api.rejectResidency).toHaveBeenCalledWith("res-1"));
  });

  it("does not show approve/reject/correct actions in admin (read-only) mode", async () => {
    vi.mocked(api.listUserResidencies).mockResolvedValue([RESIDENCY]);
    renderWithRouter(<AddressHistory userId="user-1" />);

    await screen.findByText("Kerkstraat 12, 1012AB Amsterdam");
    expect(api.listUserResidencies).toHaveBeenCalledWith("user-1");
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Correct date" })).not.toBeInTheDocument();
  });

  it("corrects the valid_from date via a prompt", async () => {
    vi.mocked(api.listMyResidencies).mockResolvedValue([RESIDENCY]);
    vi.mocked(api.correctResidency).mockResolvedValue({ ...RESIDENCY, valid_from: "2025-06-01" });
    vi.spyOn(window, "prompt").mockReturnValue("2025-06-01");
    renderWithRouter(<AddressHistory />);

    fireEvent.click(await screen.findByRole("button", { name: "Correct date" }));

    await waitFor(() =>
      expect(api.correctResidency).toHaveBeenCalledWith("res-1", { valid_from: "2025-06-01" })
    );
  });

  it("links to the source document when linked documents exist", async () => {
    vi.mocked(api.listMyResidencies).mockResolvedValue([RESIDENCY]);
    renderWithRouter(<AddressHistory />);

    const link = await screen.findByRole("link", { name: "View source document" });
    expect(link).toHaveAttribute("href", "/documents/doc-1");
  });
});
