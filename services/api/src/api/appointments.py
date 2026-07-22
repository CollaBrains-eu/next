"""Appointment CRUD (Phase 27b: calendar/appointments).

See docs/roadmap/phase-27.md (§27b) and
docs/superpowers/specs/2026-07-09-phase27b-calendar-design.md.
"""
from datetime import date, datetime, time, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.ics_utils import build_vevent_calendar, format_ics_datetime, ics_slug
from api.models import Appointment, User

router = APIRouter(tags=["appointments"])


class AppointmentOut(BaseModel):
    id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime | None
    location: str | None
    notes: str | None
    case_id: UUID | None
    vehicle_id: UUID | None
    source_task_id: UUID | None
    created_at: datetime


@router.get("/appointments", response_model=list[AppointmentOut])
async def list_appointments(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Appointment]:
    if to < from_:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'to' must not be before 'from'")

    range_start = datetime.combine(from_, time.min, tzinfo=timezone.utc)
    range_end = datetime.combine(to, time.max, tzinfo=timezone.utc)
    query = (
        select(Appointment)
        .where(Appointment.starts_at >= range_start, Appointment.starts_at <= range_end)
        .order_by(Appointment.starts_at)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


class AppointmentCreate(BaseModel):
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    location: str | None = None
    notes: str | None = None
    case_id: UUID | None = None
    vehicle_id: UUID | None = None


@router.post("/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    body: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Appointment:
    appointment = Appointment(
        title=body.title,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        location=body.location,
        notes=body.notes,
        case_id=body.case_id,
        vehicle_id=body.vehicle_id,
        created_by=current_user.id,
    )
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    return appointment


class AppointmentUpdate(BaseModel):
    title: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = None
    notes: str | None = None
    case_id: UUID | None = None
    vehicle_id: UUID | None = None


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
async def update_appointment(
    appointment_id: UUID,
    update: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Appointment:
    appointment = await db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(appointment, field, value)

    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.delete("/appointments/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    appointment = await db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    await db.delete(appointment)
    await db.commit()


def build_ics(appointment: Appointment) -> str:
    return build_vevent_calendar(
        uid=str(appointment.id),
        summary=appointment.title,
        dtstart=format_ics_datetime(appointment.starts_at),
        dtend=format_ics_datetime(appointment.ends_at) if appointment.ends_at else None,
        location=appointment.location,
        description=appointment.notes,
        prodid="-//CollaBrains//Appointments//EN",
    )


@router.get("/appointments/{appointment_id}/ics")
async def export_appointment_ics(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    appointment = await db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    ics_text = build_ics(appointment)
    slug = ics_slug(appointment.title)
    return Response(
        content=ics_text,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{slug}.ics"'},
    )
