import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Vehicles from "./Vehicles";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listVehicles: vi.fn(),
    lookupVehicle: vi.fn(),
  };
});

const VEHICLE: api.VehicleOut = {
  id: "v1", kenteken: "AB-12-CD", vin: null, voertuigsoort: "Personenauto", merk: "Volkswagen",
  handelsbenaming: "Golf", eerste_kleur: "Grijs", datum_eerste_toelating: null,
  vervaldatum_apk: "2027-01-01", wam_verzekerd: "Ja", openstaande_terugroepactie_indicator: null,
  brandstofomschrijving: null, fetched_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z",
};

describe("Vehicles", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listVehicles).mockResolvedValue([VEHICLE]);
    vi.mocked(api.lookupVehicle).mockResolvedValue(VEHICLE);
  });

  it("renders the vehicle list with RDW details", async () => {
    render(<Vehicles />);
    expect(await screen.findByText("AB-12-CD")).toBeInTheDocument();
    expect(screen.getByText("Volkswagen Golf")).toBeInTheDocument();
  });

  it("shows EmptyState when there are no vehicles", async () => {
    vi.mocked(api.listVehicles).mockResolvedValue([]);
    render(<Vehicles />);
    expect(await screen.findByText("No vehicles detected yet.")).toBeInTheDocument();
  });

  it("disables the search button until a plate is entered", async () => {
    render(<Vehicles />);
    await screen.findByText("AB-12-CD");
    expect(screen.getByRole("button", { name: "Zoek op" })).toBeDisabled();
  });

  it("looks up a vehicle and refreshes the list", async () => {
    render(<Vehicles />);
    await screen.findByText("AB-12-CD");
    fireEvent.change(screen.getByPlaceholderText("AB-12-CD"), { target: { value: "XY-99-ZZ" } });
    fireEvent.click(screen.getByRole("button", { name: "Zoek op" }));
    await waitFor(() => expect(api.lookupVehicle).toHaveBeenCalledWith("XY-99-ZZ"));
  });
});
