import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CaseDetail from "./CaseDetail";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getCase: vi.fn(),
    updateCaseStatus: vi.fn(),
    listDocuments: vi.fn(),
    listTasks: vi.fn(),
    listDecisions: vi.fn(),
    listVehicles: vi.fn(),
    linkVehicleToCase: vi.fn(),
    listCaseMembers: vi.fn(),
    inviteCaseMember: vi.fn(),
    removeCaseMember: vi.fn(),
    lookupUserByPhone: vi.fn(),
  };
});

const CASE: api.CaseDashboardOut = {
  id: "c1",
  name: "Alpha matter",
  description: "First case",
  status: "open",
  created_at: "2026-01-01T00:00:00Z",
  document_count: 0,
  member_count: 0,
  documents: [],
  tasks: [],
  decisions: [],
  vehicles: [],
  appointments: [],
  is_owner: true,
  owner_display_name: "Alice Owner",
};

const VEHICLES: api.VehicleOut[] = [
  {
    id: "v1", kenteken: "AB-12-CD", vin: null, voertuigsoort: null, merk: "Volkswagen",
    handelsbenaming: "Golf", eerste_kleur: null, datum_eerste_toelating: null,
    vervaldatum_apk: null, wam_verzekerd: null, openstaande_terugroepactie_indicator: null,
    brandstofomschrijving: null, fetched_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z",
  },
];

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/cases/c1"]}>
      <Routes>
        <Route path="/cases/:id" element={<CaseDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("CaseDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getCase).mockResolvedValue(CASE);
    vi.mocked(api.listDocuments).mockResolvedValue([]);
    vi.mocked(api.listTasks).mockResolvedValue([]);
    vi.mocked(api.listDecisions).mockResolvedValue([]);
    vi.mocked(api.listVehicles).mockResolvedValue(VEHICLES);
    vi.mocked(api.updateCaseStatus).mockResolvedValue({ ...CASE, status: "closed" });
    vi.mocked(api.linkVehicleToCase).mockResolvedValue(undefined);
    vi.mocked(api.listCaseMembers).mockResolvedValue([]);
  });

  it("renders the case name and status badge", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Alpha matter" })).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();
  });

  it("shows who owns the case, even when viewed by a non-owner", async () => {
    vi.mocked(api.getCase).mockResolvedValue({ ...CASE, is_owner: false, owner_display_name: "Bob Boss" });
    renderPage();
    await screen.findByRole("heading", { name: "Alpha matter" });
    expect(screen.getByText("Owned by Bob Boss")).toBeInTheDocument();
  });

  it("shows 'Nothing linked yet.' for each empty section", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Alpha matter" });
    expect(screen.getAllByText("Nothing linked yet.")).toHaveLength(5);
  });

  it("renders linked appointments with their formatted time", async () => {
    vi.mocked(api.getCase).mockResolvedValue({
      ...CASE,
      appointments: [{ id: "a1", title: "Site visit", starts_at: "2026-03-05T14:30:00Z" }],
    });
    renderPage();
    await screen.findByRole("heading", { name: "Alpha matter" });
    expect(screen.getByText("Site visit")).toBeInTheDocument();
  });

  it("toggles status when the status badge is clicked", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Alpha matter" });
    fireEvent.click(screen.getByText("open"));
    await waitFor(() => expect(api.updateCaseStatus).toHaveBeenCalledWith("c1", "closed"));
  });

  it("attaches a vehicle via the vehicles Attach control", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Alpha matter" });
    const vehiclesLabel = screen.getByText("Vehicles");
    const vehiclesSection = vehiclesLabel.closest("div")!.parentElement!;
    fireEvent.click(within(vehiclesSection).getByText("+ Attach"));
    fireEvent.click(within(vehiclesSection).getByPlaceholderText("Select…"));
    fireEvent.click(within(vehiclesSection).getByRole("button", { name: "AB-12-CD" }));
    fireEvent.click(within(vehiclesSection).getByRole("button", { name: "Attach" }));
    await waitFor(() => expect(api.linkVehicleToCase).toHaveBeenCalledWith("c1", "v1"));
  });

  it("shows invite controls only when is_owner is true", async () => {
    vi.mocked(api.getCase).mockResolvedValue({ ...CASE, is_owner: false });
    renderPage();
    await screen.findByRole("heading", { name: "Alpha matter" });
    expect(screen.queryByPlaceholderText("Phone number, e.g. +491511234567")).not.toBeInTheDocument();
  });

  it("looks up a user by phone, then invites them", async () => {
    vi.mocked(api.lookupUserByPhone).mockResolvedValue({ id: "u2", username: "bob", display_name: "Bob Smith" });
    vi.mocked(api.inviteCaseMember).mockResolvedValue({
      id: "m1", case_id: "c1", case_name: "Alpha matter", user_id: "u2",
      username: "bob", user_display_name: "Bob Smith", role: "member", status: "pending", created_at: "2026-01-01T00:00:00Z",
    });
    renderPage();
    await screen.findByRole("heading", { name: "Alpha matter" });

    fireEvent.change(screen.getByPlaceholderText("Phone number, e.g. +491511234567"), { target: { value: "+15559990101" } });
    fireEvent.click(screen.getByRole("button", { name: "Look up" }));

    expect(await screen.findByText("Bob Smith")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Invite" }));

    await waitFor(() => expect(api.inviteCaseMember).toHaveBeenCalledWith("c1", "u2", "member"));
  });

  it("shows an inline error when the phone lookup finds nobody, and does not invite", async () => {
    vi.mocked(api.lookupUserByPhone).mockResolvedValue(null);
    renderPage();
    await screen.findByRole("heading", { name: "Alpha matter" });

    fireEvent.change(screen.getByPlaceholderText("Phone number, e.g. +491511234567"), { target: { value: "+15559990199" } });
    fireEvent.click(screen.getByRole("button", { name: "Look up" }));

    expect(await screen.findByText("No user found with that phone number.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Invite" })).not.toBeInTheDocument();
    expect(api.inviteCaseMember).not.toHaveBeenCalled();
  });

  it("removes an accepted member and refreshes the list", async () => {
    vi.mocked(api.listCaseMembers).mockResolvedValue([
      {
        id: "m1", case_id: "c1", case_name: "Alpha matter", user_id: "u2",
        username: "bob", user_display_name: "Bob Smith", role: "member", status: "accepted", created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    vi.mocked(api.removeCaseMember).mockResolvedValue(undefined);
    renderPage();
    await screen.findByText("Bob Smith");

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(api.removeCaseMember).toHaveBeenCalledWith("c1", "u2"));
  });
});
