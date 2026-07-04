"""Vehicle list + direct lookup REST endpoints (Phase 19).

Phase 18 built `Vehicle`/`vehicle_agent.lookup_vehicle` with only a Tool
Registry entry (reachable via the Manager Agent/MCP) -- no REST surface
existed. This file adds one: a list endpoint and a direct lookup
endpoint, both new. See docs/superpowers/specs/2026-07-04-vehicles-page-design.md.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import User, Vehicle
from api.rdw_client import RdwLookupError
from api.vehicle_agent import lookup_vehicle

router = APIRouter(tags=["vehicles"])


class VehicleOut(BaseModel):
    id: UUID
    kenteken: str | None
    vin: str | None
    voertuigsoort: str | None
    merk: str | None
    handelsbenaming: str | None
    eerste_kleur: str | None
    datum_eerste_toelating: str | None
    vervaldatum_apk: str | None
    wam_verzekerd: str | None
    openstaande_terugroepactie_indicator: str | None
    brandstofomschrijving: str | None
    fetched_at: datetime | None
    created_at: datetime


@router.get("/vehicles", response_model=list[VehicleOut])
async def list_vehicles_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Vehicle]:
    result = await db.execute(select(Vehicle).order_by(Vehicle.created_at.desc()))
    return list(result.scalars().all())


class VehicleLookupRequest(BaseModel):
    kenteken: str


@router.post("/vehicles/lookup", response_model=VehicleOut)
async def lookup_vehicle_endpoint(
    request: VehicleLookupRequest,
    current_user: User = Depends(get_current_user),
) -> Vehicle:
    try:
        return await lookup_vehicle(kenteken=request.kenteken)
    except RdwLookupError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
