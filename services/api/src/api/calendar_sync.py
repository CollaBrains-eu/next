"""Calendar auto-sync: turns an appointment-category Task into a persisted
Appointment, closing the "documents... in sync with calendar" gap v2 never
solved either (v2's own calendar was stateless .ics generation, never
persisted -- see docs/superpowers/specs/2026-07-22-calendar-auto-sync-design.md).
Deliberately one-directional: editing or deleting the Task afterward does not
touch the Appointment it created.
"""
from datetime import datetime, time, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Appointment, Task


async def sync_appointment_for_task(db: AsyncSession, *, task: Task, user_id: UUID | None) -> Appointment | None:
    """Creates a linked Appointment for `task` if it's category="appointment"
    with a due_date, unless one already exists for it. Returns the created
    Appointment, or None if nothing was created."""
    if task.category != "appointment" or task.due_date is None or user_id is None:
        return None

    existing = (
        await db.execute(select(Appointment).where(Appointment.source_task_id == task.id))
    ).scalar_one_or_none()
    if existing is not None:
        return None

    appointment = Appointment(
        title=task.title,
        starts_at=datetime.combine(task.due_date, time.min, tzinfo=timezone.utc),
        notes=task.description,
        created_by=user_id,
        source_task_id=task.id,
    )
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    return appointment
