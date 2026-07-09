from unittest.mock import patch
from uuid import uuid4

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Entity, Vehicle


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _create_vehicle(kenteken: str, *, merk: str | None = None) -> Vehicle:
    async with async_session() as db:
        entity = Entity(name=kenteken, entity_type="vehicle")
        db.add(entity)
        await db.flush()
        vehicle = Vehicle(entity_id=entity.id, kenteken=kenteken, merk=merk)
        db.add(vehicle)
        await db.commit()
        await db.refresh(vehicle)
        return vehicle


async def test_list_vehicles_returns_created_vehicles(client):
    token = await _login(client, f"vehiclerouter-{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    vehicle = await _create_vehicle(f"LI-{uuid4().hex[:2].upper()}-ST", merk="TOYOTA")

    response = await client.get("/vehicles", headers=headers)

    assert response.status_code == 200
    kentekens = {v["kenteken"] for v in response.json()}
    assert vehicle.kenteken in kentekens


async def test_list_vehicles_requires_auth(client):
    response = await client.get("/vehicles")
    assert response.status_code == 401


FAKE_RDW_DATA = {
    "voertuigsoort": "Personenauto", "merk": "TOYOTA", "handelsbenaming": "AYGO",
    "eerste_kleur": "GRIJS", "datum_eerste_toelating": "20180501",
    "vervaldatum_apk": "20270501", "wam_verzekerd": "Ja",
    "openstaande_terugroepactie_indicator": "Nee", "brandstofomschrijving": "Benzine",
    "massa_ledig_voertuig": "840", "aantal_cilinders": "3", "wielbasis": "2340",
    "catalogusprijs": "12500", "aantal_zitplaatsen": "4", "aantal_deuren": "5",
    "vermogen_massarijklaar": "51", "europese_voertuigcategorie": "M1",
}


async def test_lookup_vehicle_endpoint_returns_rdw_data(client):
    token = await _login(client, f"vehiclerouter-{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("api.vehicles_router.lookup_vehicle") as mock_lookup:
        mock_lookup.return_value = await _create_vehicle("LO-01-OK", merk="TOYOTA")
        response = await client.post("/vehicles/lookup", headers=headers, json={"kenteken": "LO-01-OK"})

    assert response.status_code == 200
    assert response.json()["merk"] == "TOYOTA"


async def test_lookup_vehicle_endpoint_returns_502_on_rdw_outage(client):
    from api.rdw_client import RdwLookupError

    token = await _login(client, f"vehiclerouter-{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("api.vehicles_router.lookup_vehicle", side_effect=RdwLookupError("boom")):
        response = await client.post("/vehicles/lookup", headers=headers, json={"kenteken": "ZZ-99-ZZ"})

    assert response.status_code == 502


async def test_lookup_vehicle_endpoint_returns_404_when_rdw_confirms_not_found(client):
    token = await _login(client, f"vehiclerouter-{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("api.vehicles_router.lookup_vehicle", return_value=None):
        response = await client.post("/vehicles/lookup", headers=headers, json={"kenteken": "ZZ-97-ZZ"})

    assert response.status_code == 404
