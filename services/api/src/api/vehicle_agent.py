"""Vehicle Agent: regex-detect kentekens/VINs in document text, enrich
from RDW, and link matching vehicles across documents (Phase 18).

Detection is deliberately regex, not LLM-based -- see
docs/superpowers/specs/2026-07-04-vehicle-entity-design.md for why:
Dutch kentekens and VINs follow strict, small, fixed syntactic formats,
which a deterministic pattern matches more reliably (and for free) than
an LLM prompt. This covers the commonly-used NL kenteken "sidecodes";
older/rarer historical formats are not exhaustively covered -- an
accepted, documented limitation, not a bug.
"""
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Entity, EntityMention, Vehicle
from api.rdw_client import RdwLookupError, fetch_vehicle_data

logger = logging.getLogger(__name__)

_SEP = r"[-\s]?"
_KENTEKEN_PATTERNS = [
    rf"[A-Z]{{2}}{_SEP}\d{{2}}{_SEP}[A-Z]{{2}}",  # XX-99-XX
    rf"\d{{2}}{_SEP}[A-Z]{{2}}{_SEP}\d{{2}}",  # 99-XX-99
    rf"\d{{2}}{_SEP}\d{{2}}{_SEP}[A-Z]{{2}}",  # 99-99-XX
    rf"[A-Z]{{2}}{_SEP}\d{{2}}{_SEP}\d{{2}}",  # XX-99-99
    rf"\d{{2}}{_SEP}[A-Z]{{3}}{_SEP}\d{{1}}",  # 99-XXX-9
    rf"\d{{1}}{_SEP}[A-Z]{{3}}{_SEP}\d{{2}}",  # 9-XXX-99
    rf"[A-Z]{{2}}{_SEP}\d{{3}}{_SEP}[A-Z]{{1}}",  # XX-999-X
    rf"[A-Z]{{1}}{_SEP}\d{{3}}{_SEP}[A-Z]{{2}}",  # X-999-XX
]
KENTEKEN_RE = re.compile(r"\b(?:" + "|".join(_KENTEKEN_PATTERNS) + r")\b", re.IGNORECASE)
# 17-char VIN per ISO 3779, excluding I/O/Q (never used, to avoid 1/0 confusion).
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.IGNORECASE)


def _normalize_kenteken(raw: str) -> str:
    return raw.upper().replace("-", "").replace(" ", "")


def detect_kentekens(text: str) -> list[str]:
    return sorted({_normalize_kenteken(match) for match in KENTEKEN_RE.findall(text)})


def detect_vins(text: str) -> list[str]:
    return sorted({match.upper() for match in VIN_RE.findall(text)})


async def _get_or_create_vehicle_entity(
    db: AsyncSession, *, kenteken: str | None, vin: str | None
) -> tuple[Entity, Vehicle]:
    """Get-or-create the Entity+Vehicle pair for a detected kenteken/VIN.

    Kenteken is the dedup key once known. A VIN-only vehicle dedupes on
    VIN among rows that have no kenteken yet; if a kenteken for that same
    real-world vehicle surfaces later in a different document, a second,
    separate row is created rather than merged -- the same "no fuzzy
    resolution" stance ADR 0008 already takes for person/organization
    entities, applied here too (see the spec's Consequences section).
    """
    vehicle: Vehicle | None = None

    if kenteken is not None:
        result = await db.execute(select(Vehicle).where(Vehicle.kenteken == kenteken))
        vehicle = result.scalar_one_or_none()
    elif vin is not None:
        result = await db.execute(select(Vehicle).where(Vehicle.vin == vin, Vehicle.kenteken.is_(None)))
        vehicle = result.scalar_one_or_none()

    if vehicle is None:
        entity = Entity(name=kenteken or vin, entity_type="vehicle")
        db.add(entity)
        await db.flush()
        vehicle = Vehicle(entity_id=entity.id, kenteken=kenteken, vin=vin)
        db.add(vehicle)
        await db.flush()
    else:
        entity = await db.get(Entity, vehicle.entity_id)
        if vin is not None and vehicle.vin is None:
            vehicle.vin = vin
        if kenteken is not None and vehicle.kenteken is None:
            vehicle.kenteken = kenteken
            entity.name = kenteken

    return entity, vehicle


async def _link_mention(db: AsyncSession, entity_id: UUID, document_id: UUID) -> None:
    existing = await db.execute(
        select(EntityMention).where(EntityMention.entity_id == entity_id, EntityMention.document_id == document_id)
    )
    if existing.scalar_one_or_none() is None:
        db.add(EntityMention(entity_id=entity_id, document_id=document_id))


async def _enrich_from_rdw(vehicle: Vehicle) -> None:
    """Populate `vehicle`'s RDW fields in place. Never raises -- a
    transient failure is logged and `fetched_at` is left untouched (so a
    later document mentioning this kenteken, or a manual tool call, will
    retry); a confirmed "not found" sets `fetched_at` so it isn't retried
    on every future document automatically."""
    if vehicle.kenteken is None or vehicle.fetched_at is not None:
        return
    try:
        data = await fetch_vehicle_data(vehicle.kenteken)
    except RdwLookupError as exc:
        logger.warning("vehicle_agent: RDW lookup failed for %s: %s", vehicle.kenteken, exc)
        return
    if data is None:
        vehicle.fetched_at = datetime.now(timezone.utc)
        return
    for field, value in data.items():
        setattr(vehicle, field, value)
    vehicle.fetched_at = datetime.now(timezone.utc)


async def detect_and_link_vehicles(db: AsyncSession, *, document_id: UUID, text: str) -> list[Vehicle]:
    """Regex-detect kentekens/VINs in `text`, get-or-create Vehicle/Entity
    rows, link them to `document_id`, and enrich any newly-known kenteken
    from RDW. Commits internally (same convention as
    `entity_agent.extract_entities`) -- callers don't manage the
    transaction."""
    kentekens = detect_kentekens(text)
    vins = detect_vins(text)
    vehicles: list[Vehicle] = []

    if len(kentekens) == 1 and len(vins) == 1:
        # Exactly one of each in the same document -- treat as one vehicle.
        entity, vehicle = await _get_or_create_vehicle_entity(db, kenteken=kentekens[0], vin=vins[0])
        await _link_mention(db, entity.id, document_id)
        await _enrich_from_rdw(vehicle)
        vehicles.append(vehicle)
    else:
        for kenteken in kentekens:
            entity, vehicle = await _get_or_create_vehicle_entity(db, kenteken=kenteken, vin=None)
            await _link_mention(db, entity.id, document_id)
            await _enrich_from_rdw(vehicle)
            vehicles.append(vehicle)
        for vin in vins:
            entity, vehicle = await _get_or_create_vehicle_entity(db, kenteken=None, vin=vin)
            await _link_mention(db, entity.id, document_id)
            vehicles.append(vehicle)

    await db.commit()
    for vehicle in vehicles:
        await db.refresh(vehicle)
    return vehicles


async def lookup_vehicle(*, kenteken: str) -> Vehicle:
    """Actively look up (or force-refresh) a vehicle by kenteken -- backs
    the `lookup_vehicle` tool. Unlike the passive pipeline path, this
    always calls RDW even if `fetched_at` is already set, so a user can
    force a stale or previously-failed lookup to retry. Manages its own
    session/transaction -- the Tool Registry handler that calls this
    already consumed its own `db`/`user_id` for the permission check
    before reaching here, so this function needs no caller-supplied
    session."""
    from api.db import async_session as _async_session

    normalized = _normalize_kenteken(kenteken)
    async with _async_session() as db:
        entity, vehicle = await _get_or_create_vehicle_entity(db, kenteken=normalized, vin=None)
        try:
            data = await fetch_vehicle_data(normalized)
        except RdwLookupError:
            data = None
        if data is not None:
            for field, value in data.items():
                setattr(vehicle, field, value)
        vehicle.fetched_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(vehicle)
        return vehicle
