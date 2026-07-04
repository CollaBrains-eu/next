from uuid import uuid4

from api.db import async_session
from api.models import Entity, Vehicle


async def test_vehicle_row_round_trips_via_entity_fk():
    async with async_session() as db:
        entity = Entity(name="AB-12-CD", entity_type="vehicle")
        db.add(entity)
        await db.flush()
        vehicle = Vehicle(entity_id=entity.id, kenteken="AB12CD")
        db.add(vehicle)
        await db.commit()
        await db.refresh(vehicle)

    async with async_session() as db:
        fetched = await db.get(Vehicle, vehicle.id)
        assert fetched is not None
        assert fetched.kenteken == "AB12CD"
        assert fetched.entity_id == entity.id
