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
  };
});

const CASE: api.CaseDashboardOut = {
  id: "c1",
  name: "Alpha matter",
  description: "First case",
  status: "open",
  created_at: "2026-01-01T00:00:00Z",
  documents: [],
  tasks: [],
  decisions: [],
  vehicles: [],
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
  });

  it("renders the case name and status badge", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Alpha matter" })).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();
  });

  it("shows 'Nothing linked yet.' for each empty section", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Alpha matter" });
    expect(screen.getAllByText("Nothing linked yet.")).toHaveLength(4);
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
});
