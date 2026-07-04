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
