from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from api.db import async_session
from api.models import Document, Entity, EntityMention, User, Vehicle
from api.rdw_client import RdwLookupError
from api.vehicle_agent import detect_and_link_vehicles, detect_kentekens, detect_vins, lookup_vehicle


async def _create_document() -> Document:
    async with async_session() as db:
        user = User(username=f"vehicletestuser-{uuid4().hex[:8]}", display_name="Vehicle Test User", role="member")
        db.add(user)
        await db.flush()
        document = Document(
            owner_id=user.id, title="t", filename="t.pdf", mime_type="application/pdf",
            status="ready", ocr_text="some text",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


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


FAKE_RDW_DATA = {
    "voertuigsoort": "Personenauto", "merk": "TOYOTA", "handelsbenaming": "AYGO",
    "eerste_kleur": "GRIJS", "datum_eerste_toelating": "20180501",
    "vervaldatum_apk": "20270501", "wam_verzekerd": "Ja",
    "openstaande_terugroepactie_indicator": "Nee", "brandstofomschrijving": "Benzine",
    "massa_ledig_voertuig": "840", "aantal_cilinders": "3", "wielbasis": "2340",
    "catalogusprijs": "12500", "aantal_zitplaatsen": "4", "aantal_deuren": "5",
    "vermogen_massarijklaar": "51", "europese_voertuigcategorie": "M1",
}


async def test_detect_and_link_vehicles_creates_entity_and_enriches_from_rdw():
    document = await _create_document()
    with patch("api.vehicle_agent.fetch_vehicle_data", return_value=FAKE_RDW_DATA):
        async with async_session() as db:
            vehicles = await detect_and_link_vehicles(
                db, document_id=document.id, text="Kenteken TE-01-ST is geregistreerd."
            )
    assert len(vehicles) == 1
    assert vehicles[0].kenteken == "TE01ST"
    assert vehicles[0].merk == "TOYOTA"
    assert vehicles[0].fetched_at is not None


async def test_detect_and_link_vehicles_links_kenteken_and_vin_from_same_document():
    document = await _create_document()
    with patch("api.vehicle_agent.fetch_vehicle_data", return_value=FAKE_RDW_DATA):
        async with async_session() as db:
            vehicles = await detect_and_link_vehicles(
                db, document_id=document.id,
                text="Kenteken TE-02-ST, VIN 1HGCM82633A004352.",
            )
    assert len(vehicles) == 1
    assert vehicles[0].kenteken == "TE02ST"
    assert vehicles[0].vin == "1HGCM82633A004352"


async def test_detect_and_link_vehicles_shares_one_entity_across_two_documents():
    doc_a = await _create_document()
    doc_b = await _create_document()
    with patch("api.vehicle_agent.fetch_vehicle_data", return_value=FAKE_RDW_DATA):
        async with async_session() as db:
            first = await detect_and_link_vehicles(db, document_id=doc_a.id, text="Kenteken TE-03-ST.")
        async with async_session() as db:
            second = await detect_and_link_vehicles(db, document_id=doc_b.id, text="Kenteken TE-03-ST.")

    assert first[0].id == second[0].id
    async with async_session() as db:
        mentions = await db.execute(
            select(EntityMention).where(EntityMention.entity_id == first[0].entity_id)
        )
        assert len(mentions.scalars().all()) == 2


async def test_detect_and_link_vehicles_never_raises_on_rdw_failure():
    document = await _create_document()
    with patch("api.vehicle_agent.fetch_vehicle_data", side_effect=RdwLookupError("boom")):
        async with async_session() as db:
            vehicles = await detect_and_link_vehicles(db, document_id=document.id, text="Kenteken TE-04-ST.")
    assert len(vehicles) == 1
    assert vehicles[0].merk is None
    assert vehicles[0].fetched_at is None


async def test_lookup_vehicle_force_refreshes_even_if_already_fetched():
    with patch("api.vehicle_agent.fetch_vehicle_data", return_value=FAKE_RDW_DATA):
        vehicle_first = await lookup_vehicle(kenteken="TE-ST05")
        vehicle_second = await lookup_vehicle(kenteken="TE-ST05")
    assert vehicle_first.id == vehicle_second.id
    assert vehicle_second.fetched_at >= vehicle_first.fetched_at
