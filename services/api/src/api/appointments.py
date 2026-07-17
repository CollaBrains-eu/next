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


def _escape_ics_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _format_ics_datetime(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


def build_ics(appointment: Appointment) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CollaBrains//Appointments//EN",
        "BEGIN:VEVENT",
        f"UID:{appointment.id}@collabrains.eu",
        f"DTSTAMP:{_format_ics_datetime(datetime.now(timezone.utc))}",
        f"DTSTART:{_format_ics_datetime(appointment.starts_at)}",
    ]
    if appointment.ends_at:
        lines.append(f"DTEND:{_format_ics_datetime(appointment.ends_at)}")
    lines.append(f"SUMMARY:{_escape_ics_text(appointment.title)}")
    if appointment.location:
        lines.append(f"LOCATION:{_escape_ics_text(appointment.location)}")
    if appointment.notes:
        lines.append(f"DESCRIPTION:{_escape_ics_text(appointment.notes)}")
    lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _ics_slug(title: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "appointment"


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
    slug = _ics_slug(appointment.title)
    return Response(
        content=ics_text,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{slug}.ics"'},
    )
