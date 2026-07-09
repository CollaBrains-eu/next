import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import LicensePlateInput from "../components/LicensePlateInput";
import { Button } from "../components/ui/Button";
import { ApiError, listVehicles, lookupVehicle, type VehicleOut } from "../lib/api";

function VehicleStatus({ vehicle }: { vehicle: VehicleOut }) {
  if (vehicle.fetched_at === null) {
    return <p className="text-sm text-ink-3">Nog niet opgehaald.</p>;
  }
  if (vehicle.merk === null) {
    return <p className="text-sm text-ink-3">Geen RDW-gegevens gevonden voor dit kenteken.</p>;
  }
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
      <dt className="text-ink-2">Merk / model</dt>
      <dd className="text-ink">{vehicle.merk} {vehicle.handelsbenaming}</dd>
      <dt className="text-ink-2">Voertuigsoort</dt>
      <dd className="text-ink">{vehicle.voertuigsoort ?? "-"}</dd>
      <dt className="text-ink-2">Kleur</dt>
      <dd className="text-ink">{vehicle.eerste_kleur ?? "-"}</dd>
      <dt className="text-ink-2">APK-vervaldatum</dt>
      <dd className="text-ink">{vehicle.vervaldatum_apk ?? "-"}</dd>
      <dt className="text-ink-2">WAM-verzekerd</dt>
      <dd className="text-ink">{vehicle.wam_verzekerd ?? "-"}</dd>
    </dl>
  );
}

export default function Vehicles() {
  const { t } = useTranslation();
  const [vehicles, setVehicles] = useState<VehicleOut[]>([]);
  const [kenteken, setKenteken] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    setLoading(true);
    listVehicles()
      .then(setVehicles)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("vehicles.loadError")))
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
      setError(err instanceof ApiError ? err.message : t("vehicles.lookupError"));
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">{t("vehicles.title")}</h1>

      <Card className="flex flex-col gap-3">
        <div className="flex items-center gap-3">
          <LicensePlateInput value={kenteken} onChange={setKenteken} />
          <Button onClick={handleSearch} disabled={searching || !kenteken.trim()}>
            Zoek op
          </Button>
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
      </Card>

      {loading ? (
        <p className="text-ink-3">{t("common.loading")}</p>
      ) : vehicles.length === 0 ? (
        <EmptyState message={t("vehicles.emptyMessage")} />
      ) : (
        <div className="flex flex-col gap-3">
          {vehicles.map((vehicle) => (
            <Card key={vehicle.id}>
              <p className="mb-2 font-mono text-lg font-bold tracking-wider text-ink">{vehicle.kenteken ?? vehicle.vin}</p>
              <VehicleStatus vehicle={vehicle} />
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
