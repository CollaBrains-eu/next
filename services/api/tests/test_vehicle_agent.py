from uuid import uuid4

from api.db import async_session
from api.models import Entity, Vehicle
from api.vehicle_agent import detect_kentekens, detect_vins


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


def test_detect_kentekens_matches_common_sidecode_formats():
    text = (
        "Kenteken AB-12-CD staat op naam. Ook gezien: 12-AB-34, 12-34-AB, "
        "AB-12-34, 12-ABC-3, 1-ABC-23, AB-123-C, A-123-BC."
    )
    assert detect_kentekens(text) == sorted({
        "AB12CD", "12AB34", "1234AB", "AB1234", "12ABC3", "1ABC23", "AB123C", "A123BC",
    })


def test_detect_kentekens_ignores_plain_dates_and_numbers():
    text = "Datum: 04-07-2026. Bedrag: 123456."
    assert detect_kentekens(text) == []


def test_detect_kentekens_deduplicates_and_normalizes_case():
    text = "ab-12-cd en nogmaals AB-12-CD."
    assert detect_kentekens(text) == ["AB12CD"]


def test_detect_vins_matches_17_char_pattern():
    text = "VIN: 1HGCM82633A004352 staat in het kentekenbewijs."
    assert detect_vins(text) == ["1HGCM82633A004352"]


def test_detect_vins_ignores_shorter_or_longer_alphanumeric_runs():
    text = "Referentie ABC123 en een langere code 1HGCM82633A0043521234"
    assert detect_vins(text) == []
