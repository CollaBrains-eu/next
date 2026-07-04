import { useEffect, useState } from "react";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import LicensePlateInput from "../components/LicensePlateInput";
import { ApiError, listVehicles, lookupVehicle, type VehicleOut } from "../lib/api";

function VehicleStatus({ vehicle }: { vehicle: VehicleOut }) {
  if (vehicle.fetched_at === null) {
    return <p className="text-sm text-slate-400">Nog niet opgehaald.</p>;
  }
  if (vehicle.merk === null) {
    return <p className="text-sm text-slate-400">Geen RDW-gegevens gevonden voor dit kenteken.</p>;
  }
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
      <dt className="text-slate-500">Merk / model</dt>
      <dd>{vehicle.merk} {vehicle.handelsbenaming}</dd>
      <dt className="text-slate-500">Voertuigsoort</dt>
      <dd>{vehicle.voertuigsoort ?? "-"}</dd>
      <dt className="text-slate-500">Kleur</dt>
      <dd>{vehicle.eerste_kleur ?? "-"}</dd>
      <dt className="text-slate-500">APK-vervaldatum</dt>
      <dd>{vehicle.vervaldatum_apk ?? "-"}</dd>
      <dt className="text-slate-500">WAM-verzekerd</dt>
      <dd>{vehicle.wam_verzekerd ?? "-"}</dd>
    </dl>
  );
}

export default function Vehicles() {
  const [vehicles, setVehicles] = useState<VehicleOut[]>([]);
  const [kenteken, setKenteken] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    setLoading(true);
    listVehicles()
      .then(setVehicles)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load vehicles"))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  async function handleSearch() {
    if (!kenteken.trim()) return;
    setSearching(true);
    setError(null);
    try {
      await lookupVehicle(kenteken.trim());
      setKenteken("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to look up vehicle");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Vehicles</h1>

      <Card className="flex flex-col gap-3">
        <div className="flex items-center gap-3">
          <LicensePlateInput value={kenteken} onChange={setKenteken} />
          <button
            onClick={handleSearch}
            disabled={searching || !kenteken.trim()}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            Zoek op
          </button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </Card>

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : vehicles.length === 0 ? (
        <EmptyState message="No vehicles detected yet." />
      ) : (
        <div className="flex flex-col gap-3">
          {vehicles.map((vehicle) => (
            <Card key={vehicle.id}>
              <p className="mb-2 font-mono text-lg font-bold tracking-wider">{vehicle.kenteken ?? vehicle.vin}</p>
              <VehicleStatus vehicle={vehicle} />
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
