from datetime import date
from uuid import uuid4

from sqlalchemy import select

from api.calendar_sync import sync_appointment_for_task
from api.db import async_session
from api.models import Appointment, Task, User

DUE_DATE = date(2026, 8, 1)


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_task(owner_id, *, category: str | None, due_date: date | None) -> Task:
    async with async_session() as db:
        task = Task(title="Dentist appointment", category=category, due_date=due_date, created_by=owner_id)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task


async def test_sync_creates_appointment_for_appointment_category_task_with_due_date():
    user = await _create_user(_unique("syncuser"))
    task = await _create_task(user.id, category="appointment", due_date=DUE_DATE)

    async with async_session() as db:
        appointment = await sync_appointment_for_task(db, task=task, user_id=user.id)

    assert appointment is not None
    assert appointment.title == "Dentist appointment"
    assert appointment.source_task_id == task.id
    assert appointment.created_by == user.id
    assert appointment.starts_at.date() == DUE_DATE


async def test_sync_is_noop_for_non_appointment_category():
    user = await _create_user(_unique("syncnoncatuser"))
    task = await _create_task(user.id, category="deadline", due_date=DUE_DATE)

    async with async_session() as db:
        result = await sync_appointment_for_task(db, task=task, user_id=user.id)

    assert result is None


async def test_sync_is_noop_when_category_is_none():
    user = await _create_user(_unique("syncnocatuser"))
    task = await _create_task(user.id, category=None, due_date=DUE_DATE)

    async with async_session() as db:
        result = await sync_appointment_for_task(db, task=task, user_id=user.id)

    assert result is None


async def test_sync_is_noop_when_due_date_is_none():
    user = await _create_user(_unique("syncnoduedateuser"))
    task = await _create_task(user.id, category="appointment", due_date=None)

    async with async_session() as db:
        result = await sync_appointment_for_task(db, task=task, user_id=user.id)

    assert result is None


async def test_sync_is_noop_when_user_id_is_none():
    user = await _create_user(_unique("syncnouseruser"))
    task = await _create_task(user.id, category="appointment", due_date=DUE_DATE)

    async with async_session() as db:
        result = await sync_appointment_for_task(db, task=task, user_id=None)

    assert result is None


async def test_sync_is_idempotent_when_an_appointment_already_exists_for_the_task():
    user = await _create_user(_unique("syncdedupuser"))
    task = await _create_task(user.id, category="appointment", due_date=DUE_DATE)

    async with async_session() as db:
        first = await sync_appointment_for_task(db, task=task, user_id=user.id)
    async with async_session() as db:
        second = await sync_appointment_for_task(db, task=task, user_id=user.id)

    assert first is not None
    assert second is None

    async with async_session() as db:
        count = len(
            (await db.execute(select(Appointment).where(Appointment.source_task_id == task.id))).scalars().all()
        )
    assert count == 1
