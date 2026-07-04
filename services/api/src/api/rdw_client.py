"""RDW open data client (Phase 18).

Anonymous access (no App Token yet) against opendata.rdw.nl's
"Gekentekende voertuigen" dataset and its fuel-type sub-dataset --
both public Socrata/SODA endpoints, keyed on kenteken only (VIN is not
in the public dataset -- RDW doesn't publish it, for privacy). See
docs/superpowers/specs/2026-07-04-vehicle-entity-design.md.

`settings.rdw_app_token` is read here but unused today (empty string);
wiring it in later (once the user has one) is a one-line addition to
`_params()`, not a call-site change.
"""
import httpx

from api.config import settings

RDW_VEHICLES_URL = "https://opendata.rdw.nl/resource/m9d7-ebf2.json"
RDW_FUEL_URL = "https://opendata.rdw.nl/resource/8ys7-d773.json"

# Verified against a real live RDW record (kenteken TT249H) during
# implementation -- "lengte" was in the originally planned field list but
# does not actually exist on this dataset, so it's omitted here rather
# than kept as a field that would always silently be None.
_VEHICLE_FIELDS = [
    "voertuigsoort", "merk", "handelsbenaming", "eerste_kleur",
    "datum_eerste_toelating", "vervaldatum_apk", "wam_verzekerd",
    "openstaande_terugroepactie_indicator", "massa_ledig_voertuig",
    "aantal_cilinders", "wielbasis", "catalogusprijs", "aantal_zitplaatsen",
    "aantal_deuren", "vermogen_massarijklaar", "europese_voertuigcategorie",
]


class RdwLookupError(RuntimeError):
    """A transient RDW failure (timeout, 5xx, rate-limit) -- distinct from
    a confirmed "no such kenteken" (which returns None, not an error)."""


def _params(kenteken: str) -> dict[str, str]:
    params = {"kenteken": kenteken}
    if settings.rdw_app_token:
        params["$$app_token"] = settings.rdw_app_token
    return params


async def fetch_vehicle_data(kenteken: str) -> dict | None:
    """Look up a vehicle by kenteken. Returns None if RDW has no record
    (a real, confirmed "not found" -- the SODA API returns 200 with an
    empty array for a filter that matches nothing, not a 404). Raises
    RdwLookupError on timeout/5xx/rate-limit so callers can tell "we
    don't know" apart from "we couldn't ask"."""
    params = _params(kenteken)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            vehicle_response = await client.get(RDW_VEHICLES_URL, params=params)
            vehicle_response.raise_for_status()
            fuel_response = await client.get(RDW_FUEL_URL, params=params)
            fuel_response.raise_for_status()
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.HTTPError) as exc:
        raise RdwLookupError(f"RDW lookup failed for {kenteken!r}: {exc}") from exc

    vehicle_rows = vehicle_response.json()
    if not vehicle_rows:
        return None

    vehicle = vehicle_rows[0]
    fuel_rows = fuel_response.json()
    fuel = fuel_rows[0] if fuel_rows else {}

    result = {field: vehicle.get(field) for field in _VEHICLE_FIELDS}
    result["brandstofomschrijving"] = fuel.get("brandstof_omschrijving")
    return result
