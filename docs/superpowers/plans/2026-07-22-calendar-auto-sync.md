# Calendar Auto-Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make appointment-like tasks show up on the calendar automatically —
extracted tasks get auto-categorized (payment/appointment/deadline/notification),
and any task that ends up with `category="appointment"` and a `due_date` gets a
linked, persisted `Appointment` row, regardless of whether that category came from
extraction, manual creation, or a manual edit.

**Architecture:** `planner_agent.py`'s existing single extraction LLM call is
extended to also return a category per task (no new LLM round-trip). A new
`calendar_sync.py` module holds `sync_appointment_for_task`, a small idempotent
function called from all three places a task's category can end up set:
`planner_agent.extract_tasks`, `tasks.create_task`, `tasks.update_task`. A new
nullable `Appointment.source_task_id` FK traces an auto-created appointment back
to its task.

**Tech Stack:** FastAPI + async SQLAlchemy + pytest (backend only — no frontend
changes; the existing Appointments/calendar UI already renders any `Appointment`
row regardless of how it was created).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-22-calendar-auto-sync-design.md`.
- No local Postgres/Docker in this dev environment — verify via the
  rsync-to-server-then-`docker compose exec -T api uv run pytest` round trip
  established in prior sub-projects, against `root@178.254.22.178`,
  repo at `/opt/collabrains`.
- Disposable-test-user pattern: every test creates its own uniquely-suffixed user
  (`f"{base}-{uuid4().hex[:8]}"`) — the test Postgres is shared, not
  transaction-isolated across runs.
- Current alembic head at plan-writing time: `7c966d7eebf4`
  (`add metafields to documents`). Verify with
  `docker compose exec -T api uv run alembic heads` before Task 2's migration —
  update `down_revision` if it has changed.
- One-directional sync only: editing or deleting a `Task` after its `Appointment`
  was created must NOT touch the `Appointment`. Do not add that in any task below.
- No frontend changes in this plan — confirmed in the spec review.

---

### Task 1: Move `TASK_CATEGORIES` + auto-categorize tasks during extraction

**Files:**
- Modify: `services/api/src/api/models.py` (add `TASK_CATEGORIES` constant, just
  above the `Task` class)
- Modify: `services/api/src/api/tasks.py` (remove local `TASK_CATEGORIES`
  definition, import from `models` instead)
- Modify: `services/api/src/api/planner_agent.py` (`EXTRACTION_PROMPT`,
  `EXTRACTION_SCHEMA`, task-building loop)
- Test: `services/api/tests/test_tasks.py` (new cases appended)

**Interfaces:**
- Produces: `api.models.TASK_CATEGORIES: tuple[str, ...]` — consumed by Task 3's
  `calendar_sync.py` indirectly via `Task.category` values it checks against, and
  directly by `tasks.py`.
- `Task.category` is now populated automatically by `extract_tasks` when the LLM
  response includes a recognized value — consumed by Task 2/3's sync logic.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_tasks.py` (after the existing
`test_extract_tasks_persists_parsed_items` test, same file/pattern):

```python
async def test_extract_tasks_persists_category_when_provided(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Dentist appointment booked for 2026-08-01.")

    fake_llm_output = (
        '[{"title": "Attend dentist appointment", "description": null, '
        '"due_date": "2026-08-01", "assignee": null, "category": "appointment"}]'
    )
    with patch("api.planner_agent.chat_completion", return_value=fake_llm_output):
        response = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["category"] == "appointment"


async def test_extract_tasks_defaults_invalid_category_to_none(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    fake_llm_output = '[{"title": "Do a thing", "category": "not-a-real-category"}]'
    with patch("api.planner_agent.chat_completion", return_value=fake_llm_output):
        response = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["category"] is None


async def test_extract_tasks_defaults_missing_category_to_none(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    with patch("api.planner_agent.chat_completion", return_value='[{"title": "Do a thing"}]'):
        response = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["category"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api uv run pytest tests/test_tasks.py -v -k category`
Expected: the two "persists_category"/"none" tests FAIL — the LLM response's
`category` key is currently ignored by `extract_tasks`.

- [ ] **Step 3: Move `TASK_CATEGORIES` into `models.py`**

In `services/api/src/api/models.py`, immediately before `class Task(Base):`:

```python
# Shared with planner_agent.py (auto-categorization) and tasks.py (manual
# create/update validation) -- lives here rather than tasks.py to avoid a
# circular import (tasks.py already imports from planner_agent.py).
TASK_CATEGORIES = ("payment", "appointment", "deadline", "notification")


class Task(Base):
```

In `services/api/src/api/tasks.py`, replace:

```python
TASK_STATUSES = ("open", "in_progress", "done")
RECURRENCE_RULES = ("daily", "weekly", "monthly")
# v2 parity ("betaling"/"afspraak"/"deadline"/"melding"): typed categories for
# action items, purely descriptive -- no behavior currently keys off category.
TASK_CATEGORIES = ("payment", "appointment", "deadline", "notification")
```

with:

```python
TASK_STATUSES = ("open", "in_progress", "done")
RECURRENCE_RULES = ("daily", "weekly", "monthly")
```

and change the import line:

```python
from api.models import CaseMember, Document, Task, User
```

to:

```python
from api.models import CaseMember, Document, Task, TASK_CATEGORIES, User
```

- [ ] **Step 4: Extend the extraction prompt, schema, and parsing**

In `services/api/src/api/planner_agent.py`, change the import line:

```python
from api.models import Task
```

to:

```python
from api.models import TASK_CATEGORIES, Task
```

Replace `EXTRACTION_PROMPT` and `EXTRACTION_SCHEMA`:

```python
EXTRACTION_PROMPT = """Extract actionable tasks from the following document. \
This includes explicit to-dos AND any scheduled appointment, deadline, or date \
the reader needs to act on or attend -- e.g. a line saying an appointment has \
been booked for a given date counts as a task like "Attend appointment on \
[date]", even if the document never phrases it as an instruction. \
Return ONLY a JSON array (no prose, no markdown fences), where each item has:
- "title": short imperative description (required)
- "description": one sentence of extra context, or null
- "due_date": an ISO date "YYYY-MM-DD" if a concrete date is mentioned, otherwise null
- "assignee": a person or role name if mentioned, otherwise null
- "category": one of {categories} if the task clearly fits one, otherwise null

If there are truly no actionable tasks or dates to act on, return an empty array: []

Document:
{text}"""

EXTRACTION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": ["string", "null"]},
            "due_date": {"type": ["string", "null"]},
            "assignee": {"type": ["string", "null"]},
            "category": {"type": ["string", "null"], "enum": [*TASK_CATEGORIES, None]},
        },
        "required": ["title"],
    },
}
```

Update the prompt-formatting call inside `extract_tasks`:

```python
    prompt = EXTRACTION_PROMPT.format(text=text[:8000])
```

to:

```python
    prompt = EXTRACTION_PROMPT.format(text=text[:8000], categories=" | ".join(f'"{c}"' for c in TASK_CATEGORIES))
```

Update the task-building loop:

```python
    tasks: list[Task] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        task = Task(
            document_id=document_id,
            title=str(item["title"])[:500],
            description=item.get("description") or None,
            due_date=_parse_due_date(item.get("due_date")),
            assignee=item.get("assignee") or None,
            source=source,
            created_by=user_id,
        )
        db.add(task)
        tasks.append(task)
```

to:

```python
    tasks: list[Task] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        category = item.get("category")
        if category not in TASK_CATEGORIES:
            category = None
        task = Task(
            document_id=document_id,
            title=str(item["title"])[:500],
            description=item.get("description") or None,
            due_date=_parse_due_date(item.get("due_date")),
            assignee=item.get("assignee") or None,
            category=category,
            source=source,
            created_by=user_id,
        )
        db.add(task)
        tasks.append(task)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T api uv run pytest tests/test_tasks.py -v`
Expected: PASS, including the pre-existing
`test_extract_tasks_persists_parsed_items` (its `EXTRACTION_SCHEMA` equality
assertion picks up the new shape automatically since it imports the live
constant).

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/models.py services/api/src/api/tasks.py services/api/src/api/planner_agent.py \
  services/api/tests/test_tasks.py
git commit -m "feat: auto-categorize extracted tasks (payment/appointment/deadline/notification)"
```

---

### Task 2: `Appointment.source_task_id` + `calendar_sync.py`

**Files:**
- Modify: `services/api/src/api/models.py` (`Appointment.source_task_id`)
- Create: `services/api/alembic/versions/8aa5b9c764d2_add_source_task_id_to_appointments.py`
- Create: `services/api/src/api/calendar_sync.py`
- Modify: `services/api/src/api/appointments.py` (`AppointmentOut.source_task_id`)
- Test: `services/api/tests/test_calendar_sync.py`

**Interfaces:**
- Produces: `sync_appointment_for_task(db, *, task: Task, user_id: UUID | None) -> Appointment | None`
  — consumed by Task 3's three hook sites.
- Consumes: `Task.category`/`Task.due_date` (Task 1), `Appointment` (existing model).

- [ ] **Step 1: Write the failing tests**

Create `services/api/tests/test_calendar_sync.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api uv run pytest tests/test_calendar_sync.py -v`
Expected: FAIL/ERROR — `api.calendar_sync` does not exist yet, and
`Appointment.source_task_id` doesn't exist yet.

- [ ] **Step 3: Add the migration**

Create `services/api/alembic/versions/8aa5b9c764d2_add_source_task_id_to_appointments.py`:

```python
"""add source_task_id to appointments

Revision ID: 8aa5b9c764d2
Revises: 7c966d7eebf4
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8aa5b9c764d2"
down_revision: Union[str, None] = "7c966d7eebf4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("source_task_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_appointments_source_task_id", "appointments", "tasks", ["source_task_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_appointments_source_task_id", "appointments", type_="foreignkey")
    op.drop_column("appointments", "source_task_id")
```

If `7c966d7eebf4` is no longer the head, update `down_revision` to match the
actual current head first.

- [ ] **Step 4: Add the `source_task_id` column to the `Appointment` model**

In `services/api/src/api/models.py`, in the `Appointment` class, add the new
column between `vehicle_id` and `created_by`:

```python
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
```

- [ ] **Step 5: Implement `calendar_sync.py`**

Create `services/api/src/api/calendar_sync.py`:

```python
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
```

- [ ] **Step 6: Expose `source_task_id` on the API**

In `services/api/src/api/appointments.py`, add the field to `AppointmentOut`:

```python
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
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `docker compose exec -T api uv run pytest tests/test_calendar_sync.py -v`
Expected: PASS (6 tests).

- [ ] **Step 8: Commit**

```bash
git add services/api/src/api/models.py services/api/src/api/calendar_sync.py \
  services/api/src/api/appointments.py \
  services/api/alembic/versions/8aa5b9c764d2_add_source_task_id_to_appointments.py \
  services/api/tests/test_calendar_sync.py
git commit -m "feat: add Appointment.source_task_id + sync_appointment_for_task"
```

---

### Task 3: Wire the sync hook into all three task-category call sites

**Files:**
- Modify: `services/api/src/api/planner_agent.py` (call sync after each extracted
  task)
- Modify: `services/api/src/api/tasks.py` (call sync in `create_task` and
  `update_task`, including the spawned recurrence task)
- Test: `services/api/tests/test_tasks.py` (new end-to-end cases appended)

**Interfaces:**
- Consumes: `sync_appointment_for_task` (Task 2).

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_tasks.py`:

```python
async def test_extracted_appointment_task_creates_a_linked_appointment(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Dentist appointment booked for 2026-08-01.")

    fake_llm_output = (
        '[{"title": "Attend dentist appointment", "description": null, '
        '"due_date": "2026-08-01", "assignee": null, "category": "appointment"}]'
    )
    with patch("api.planner_agent.chat_completion", return_value=fake_llm_output):
        extracted = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)
    task_id = extracted.json()[0]["id"]

    appointments = await client.get(
        "/appointments", headers=headers, params={"from": "2026-07-01", "to": "2026-08-31"}
    )
    matching = [a for a in appointments.json() if a["source_task_id"] == task_id]
    assert len(matching) == 1
    assert matching[0]["title"] == "Attend dentist appointment"


async def test_creating_a_task_with_appointment_category_creates_a_linked_appointment(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/tasks", headers=headers,
        json={"title": "Yearly checkup", "due_date": "2026-08-05", "category": "appointment"},
    )
    task_id = created.json()["id"]

    appointments = await client.get(
        "/appointments", headers=headers, params={"from": "2026-07-01", "to": "2026-08-31"}
    )
    matching = [a for a in appointments.json() if a["source_task_id"] == task_id]
    assert len(matching) == 1
    assert matching[0]["title"] == "Yearly checkup"


async def test_setting_a_tasks_category_to_appointment_via_patch_creates_a_linked_appointment(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/tasks", headers=headers, json={"title": "Follow-up call", "due_date": "2026-08-10"})
    task_id = created.json()["id"]

    await client.patch(f"/tasks/{task_id}", headers=headers, json={"status": "open", "category": "appointment"})

    appointments = await client.get(
        "/appointments", headers=headers, params={"from": "2026-07-01", "to": "2026-08-31"}
    )
    matching = [a for a in appointments.json() if a["source_task_id"] == task_id]
    assert len(matching) == 1


async def test_patching_a_task_twice_does_not_create_duplicate_appointments(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/tasks", headers=headers,
        json={"title": "Repeat check", "due_date": "2026-08-12", "category": "appointment"},
    )
    task_id = created.json()["id"]

    await client.patch(
        f"/tasks/{task_id}", headers=headers, json={"status": "in_progress", "category": "appointment"}
    )

    appointments = await client.get(
        "/appointments", headers=headers, params={"from": "2026-07-01", "to": "2026-08-31"}
    )
    matching = [a for a in appointments.json() if a["source_task_id"] == task_id]
    assert len(matching) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api uv run pytest tests/test_tasks.py -v -k "linked_appointment or duplicate_appointments"`
Expected: FAIL — no `Appointment` rows are created yet from any of these three
call sites.

- [ ] **Step 3: Hook `extract_tasks`**

In `services/api/src/api/planner_agent.py`, add the import:

```python
from api.calendar_sync import sync_appointment_for_task
```

Change the end of `extract_tasks`:

```python
    if tasks:
        await db.commit()
        for task in tasks:
            await db.refresh(task)
    return tasks
```

to:

```python
    if tasks:
        await db.commit()
        for task in tasks:
            await db.refresh(task)
            await sync_appointment_for_task(db, task=task, user_id=user_id)
    return tasks
```

- [ ] **Step 4: Hook `create_task` and `update_task`**

In `services/api/src/api/tasks.py`, add the import:

```python
from api.calendar_sync import sync_appointment_for_task
```

In `create_task`, change:

```python
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task
```

(the one inside `create_task`, not `update_task`) to:

```python
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await sync_appointment_for_task(db, task=task, user_id=current_user.id)
    return task
```

In `update_task`, capture the spawned recurrence task instead of discarding it,
and sync both it and the updated task. Change:

```python
    # Completing a recurring task spawns its next occurrence as a new row,
    # rather than rolling this one's due_date forward in place -- keeps a
    # real history of completed occurrences instead of silently resetting one.
    if update.status == "done" and task.status != "done" and task.recurrence_rule and task.due_date:
        db.add(
            Task(
                document_id=task.document_id,
                title=task.title,
                description=task.description,
                due_date=next_due_date(task.due_date, task.recurrence_rule),
                assignee=task.assignee,
                source=task.source,
                created_by=task.created_by,
                recurrence_rule=task.recurrence_rule,
                category=task.category,
            )
        )

    if update.due_date is not None:
        task.due_date = update.due_date
        task.notified_at = None
    if update.recurrence_rule is not None:
        task.recurrence_rule = update.recurrence_rule
    if update.category is not None:
        task.category = update.category

    task.status = update.status
    await db.commit()
    await db.refresh(task)
    return task
```

to:

```python
    # Completing a recurring task spawns its next occurrence as a new row,
    # rather than rolling this one's due_date forward in place -- keeps a
    # real history of completed occurrences instead of silently resetting one.
    spawned_task: Task | None = None
    if update.status == "done" and task.status != "done" and task.recurrence_rule and task.due_date:
        spawned_task = Task(
            document_id=task.document_id,
            title=task.title,
            description=task.description,
            due_date=next_due_date(task.due_date, task.recurrence_rule),
            assignee=task.assignee,
            source=task.source,
            created_by=task.created_by,
            recurrence_rule=task.recurrence_rule,
            category=task.category,
        )
        db.add(spawned_task)

    if update.due_date is not None:
        task.due_date = update.due_date
        task.notified_at = None
    if update.recurrence_rule is not None:
        task.recurrence_rule = update.recurrence_rule
    if update.category is not None:
        task.category = update.category

    task.status = update.status
    await db.commit()
    await db.refresh(task)
    await sync_appointment_for_task(db, task=task, user_id=current_user.id)
    if spawned_task is not None:
        await db.refresh(spawned_task)
        await sync_appointment_for_task(db, task=spawned_task, user_id=current_user.id)
    return task
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T api uv run pytest tests/test_tasks.py -v`
Expected: PASS, full file.

- [ ] **Step 6: Run the full backend regression suite**

Run: `docker compose exec -T api uv run pytest -q`
Expected: PASS, no regressions. Before running, confirm no orphaned pytest
processes are already running server-side (check via the `/proc` cmdline scan
technique, not `ps`, which isn't installed in the `api` container) — a prior
sub-project's stray concurrent runs caused a slow, contended run once.

- [ ] **Step 7: Commit**

```bash
git add services/api/src/api/planner_agent.py services/api/src/api/tasks.py \
  services/api/tests/test_tasks.py
git commit -m "feat: auto-create calendar appointments for appointment-category tasks"
```

---

## Deployment

Same workflow as the metafields+UI sub-project:

1. Push to `main` (direct commits, no PR flow).
2. On the server: `git pull` (check `git status`/`git diff origin/main` first if
   any test round-trip left rsync'd files behind, same as before — discard only
   after confirming they're byte-identical to the incoming commit).
3. Backend deploys automatically via uvicorn `--reload`.
4. Run the migration: `docker compose exec -T api uv run alembic upgrade head`.
5. No frontend rebuild needed — this sub-project has no frontend changes.
6. Verify: create a task with `category="appointment"` and a `due_date` via
   `POST /tasks`, then `GET /appointments?from=...&to=...` and confirm a matching
   `source_task_id` appears.
