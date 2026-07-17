# Appointments/Calendar (Phase 27b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `/calendar` page (month grid + agenda pane) backed by a new `Appointment` model, with full create/edit/delete and a per-event `.ics` export, per the approved spec at `docs/superpowers/specs/2026-07-09-phase27b-calendar-design.md` and `docs/roadmap/phase-27.md` (§27b).

**Architecture:** A new, separate `Appointment` table (not an extension of `Task` — appointments need time-of-day and a location, `Task.due_date` is date-only). A new `appointments.py` FastAPI router with standard CRUD plus a hand-rolled `.ics` export endpoint. A new `Calendar.tsx` route rendering a month grid (`CalendarGrid` primitive) and an agenda pane, with `Modal`-based create/edit and a second confirm-`Modal` for delete — the same two-modal pattern `DocumentDetail.tsx` already uses.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic (backend), React + Vite + TypeScript + Tailwind + Vitest/Testing Library (frontend), existing `Modal` primitive. No new dependencies (no `icalendar` package — a single `VEVENT` is hand-rolled text).

## Global Constraints

- All ids are `UUID` (`UUID(as_uuid=True)`, `default=uuid.uuid4`) — every table in this codebase uses this, no exceptions.
- No `organization_id` on `Appointment` — per-table tenant isolation is a deliberately deferred Phase 14 follow-up (ADR 0029); global visibility to all authenticated users, same as `Task`/`Case` today.
- `GET /appointments` requires both `from` and `to` query params (inclusive date range) — the frontend always asks for the visible month grid's full range, never an unbounded list.
- Frontend auth is bearer-token-in-`localStorage` (`apps/web/src/lib/api.ts`), **not cookies** — the `.ics` download must go through `fetch` + a blob URL, never a bare `<a href download>`, or the request won't carry the `Authorization` header.
- `infra/caddy/Caddyfile`'s `@api` path matcher (`infra/caddy/Caddyfile:20`) must get `/appointments*` added in the **same commit** as the router — this exact step has been missed and had to be fixed after the fact twice already in this project (ADR 0039, ADR 0043).
- `case_id` and `vehicle_id` exist on the model and API but the v1 UI has no case/vehicle picker — same "field exists, UI doesn't surface it yet" choice already made for `Task`/Kanban in Phase 27a.
- Out of scope for v1 (do not implement): recurring appointments, real Maps API integration (geocoding/embedded map), `.ics` *import*, any push/email/Signal notification tied to an appointment.
- Backend tests run via the already-provisioned local venv at `/Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/` (has `pytest`, `alembic`, and this worktree's `api` package installed editable — confirmed working). Default `DATABASE_URL` (`services/api/src/api/config.py`) is `postgresql+asyncpg://collabrains:changeme@localhost:5432/collabrains` — no env vars need to be set as long as a local Postgres with that role/db exists and is migrated.
- Frontend commands run from `apps/web/` via `pnpm test` (vitest) / `pnpm exec tsc -b`.

---

## Task 1: Local Postgres test environment + `Appointment` model + migration

**Files:**
- Modify: `services/api/src/api/models.py` (add `Appointment` class after `Vehicle`)
- Create: `services/api/alembic/versions/d3f8a1c6b9e4_create_appointments_table.py`

**Interfaces:**
- Produces: `Appointment` SQLAlchemy model (`services/api/src/api/models.py`) with columns `id: uuid.UUID`, `title: str`, `starts_at: datetime`, `ends_at: datetime | None`, `location: str | None`, `notes: str | None`, `case_id: uuid.UUID | None`, `vehicle_id: uuid.UUID | None`, `created_by: uuid.UUID`, `created_at: datetime` — consumed by Task 2's router.

- [ ] **Step 1: Start a local Postgres 16 instance for testing**

This worktree has no running local Postgres yet (confirmed: `psql` to `localhost:5432` refuses connection). Homebrew's `postgres`/`initdb`/`pg_ctl` (v16.14) are installed at `/usr/local/bin/`. Create a fresh throwaway cluster in this job's scratch dir:

```bash
mkdir -p /Users/stagnaat/.claude/jobs/2ca9e950/tmp/pgdata
/usr/local/bin/initdb -D /Users/stagnaat/.claude/jobs/2ca9e950/tmp/pgdata
/usr/local/bin/pg_ctl -D /Users/stagnaat/.claude/jobs/2ca9e950/tmp/pgdata -l /Users/stagnaat/.claude/jobs/2ca9e950/tmp/pg.log start
/usr/local/bin/psql postgres -c "CREATE ROLE collabrains WITH LOGIN SUPERUSER PASSWORD 'changeme';"
/usr/local/bin/createdb -O collabrains collabrains
```

Expected: no errors; `psql "postgresql://collabrains:changeme@localhost:5432/collabrains" -c '\dt'` returns an empty table list (schema is empty until migrations run).

- [ ] **Step 2: Add the `Appointment` model**

In `services/api/src/api/models.py`, insert immediately after the `Vehicle` class (before `BugReport`):

```python
class Appointment(Base):
    """A scheduled event with a specific time (unlike Task.due_date, which
    is date-only) and an optional physical location, for the calendar/
    agenda page and .ics export. Optionally linked to a Case and/or a
    Vehicle -- e.g. an RDW APK inspection tied to a specific kenteken.
    See docs/superpowers/specs/2026-07-09-phase27b-calendar-design.md.
    """

    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

All symbols used here (`Mapped`, `mapped_column`, `UUID`, `String`, `Text`, `DateTime`, `ForeignKey`, `func`, `uuid`, `datetime`) are already imported at the top of `models.py` for the neighboring `Vehicle`/`Task`/`Case` classes — no new imports needed.

- [ ] **Step 3: Create the migration**

Create `services/api/alembic/versions/d3f8a1c6b9e4_create_appointments_table.py`:

```python
"""create appointments table (Phase 27b, calendar/appointments)

Revision ID: d3f8a1c6b9e4
Revises: 1a9b3c5d7e2f
Create Date: 2026-07-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3f8a1c6b9e4"
down_revision: Union[str, None] = "1a9b3c5d7e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_appointments_starts_at", "appointments", ["starts_at"])


def downgrade() -> None:
    op.drop_index("ix_appointments_starts_at", table_name="appointments")
    op.drop_table("appointments")
```

- [ ] **Step 4: Apply and round-trip the migration**

```bash
cd services/api
/Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/alembic upgrade head
/Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/alembic downgrade -1
/Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/alembic upgrade head
```

Expected: all three commands exit 0 with no traceback; final state is at `d3f8a1c6b9e4`. Verify: `psql "postgresql://collabrains:changeme@localhost:5432/collabrains" -c '\d appointments'` shows all 10 columns and the FK constraints.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/models.py services/api/alembic/versions/d3f8a1c6b9e4_create_appointments_table.py
git commit -m "Add Appointment model and migration (Phase 27b)"
```

---

## Task 2: Appointments CRUD router

**Files:**
- Create: `services/api/src/api/appointments.py`
- Modify: `services/api/src/api/main.py` (register router)
- Modify: `infra/caddy/Caddyfile:20` (add `/appointments*` to `@api` matcher)
- Test: `services/api/tests/test_appointments.py`

**Interfaces:**
- Consumes: `Appointment` model from Task 1 (`services/api/src/api/models.py`); `get_db` (`api.db`), `get_current_user` (`api.auth`).
- Produces: `router` (`APIRouter`, `services/api/src/api/appointments.py`) with `GET/POST /appointments`, `PATCH/DELETE /appointments/{id}` — consumed by `main.py` (Task 2) and Task 3's `.ics` endpoint (added to the same router/file).

- [ ] **Step 1: Write the failing tests**

Create `services/api/tests/test_appointments.py`:

```python
from unittest.mock import patch

from api.ldap_auth import LdapIdentity


async def _login(client) -> str:
    identity = LdapIdentity(
        username="calendaruser", display_name="Calendar User", email="calendaruser@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "calendaruser", "password": "whatever"})
    return response.json()["access_token"]


async def test_create_appointment(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/appointments",
        headers=headers,
        json={"title": "APK inspection", "starts_at": "2026-07-14T09:30:00Z", "location": "RDW Keuringsstation, Arnhem"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "APK inspection"
    assert body["location"] == "RDW Keuringsstation, Arnhem"
    assert body["case_id"] is None
    assert body["vehicle_id"] is None


async def test_list_appointments_filters_by_date_range(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post("/appointments", headers=headers, json={"title": "In range", "starts_at": "2026-07-14T09:30:00Z"})
    await client.post("/appointments", headers=headers, json={"title": "Out of range", "starts_at": "2026-08-01T09:30:00Z"})

    response = await client.get("/appointments", headers=headers, params={"from": "2026-07-01", "to": "2026-07-31"})

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == ["In range"]


async def test_list_appointments_requires_from_and_to(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/appointments", headers=headers)

    assert response.status_code == 422


async def test_update_appointment_edits_fields(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post(
        "/appointments", headers=headers, json={"title": "Original", "starts_at": "2026-07-14T09:30:00Z"}
    )
    appointment_id = create.json()["id"]

    response = await client.patch(
        f"/appointments/{appointment_id}", headers=headers, json={"title": "Updated", "location": "New spot"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Updated"
    assert body["location"] == "New spot"


async def test_update_appointment_rejects_unknown_id(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        "/appointments/00000000-0000-0000-0000-000000000000", headers=headers, json={"title": "x"}
    )

    assert response.status_code == 404


async def test_delete_appointment_removes_it(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post(
        "/appointments", headers=headers, json={"title": "To delete", "starts_at": "2026-07-14T09:30:00Z"}
    )
    appointment_id = create.json()["id"]

    delete_response = await client.delete(f"/appointments/{appointment_id}", headers=headers)
    assert delete_response.status_code == 204

    list_response = await client.get("/appointments", headers=headers, params={"from": "2026-07-01", "to": "2026-07-31"})
    assert list_response.json() == []


async def test_appointments_require_auth(client):
    response = await client.get("/appointments", params={"from": "2026-07-01", "to": "2026-07-31"})
    assert response.status_code == 401

    response = await client.post("/appointments", json={"title": "x", "starts_at": "2026-07-14T09:30:00Z"})
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/pytest tests/test_appointments.py -v`
Expected: FAIL — `ModuleNotFoundError` or `404` on every request (no `/appointments` route registered yet).

- [ ] **Step 3: Write the router**

Create `services/api/src/api/appointments.py`:

```python
"""Appointment CRUD (Phase 27b: calendar/appointments).

See docs/roadmap/phase-27.md (§27b) and
docs/superpowers/specs/2026-07-09-phase27b-calendar-design.md.
"""
from datetime import date, datetime, time, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
```

- [ ] **Step 4: Register the router in `main.py`**

In `services/api/src/api/main.py`, add the import alphabetically (between `admin_router` and `auth_router`):

```python
from api.admin_router import router as admin_router
from api.appointments import router as appointments_router
from api.auth import router as auth_router
```

And add the registration at the end of the `include_router` block (after `onboarding_router`, matching this file's "newest feature last" ordering):

```python
app.include_router(onboarding_router)
app.include_router(appointments_router)
```

- [ ] **Step 5: Add `/appointments*` to the Caddyfile in the same commit**

In `infra/caddy/Caddyfile:20`, the `@api` path matcher currently ends `... /admin* /facts* /categories*`. Append `/appointments*`:

```
		path /auth* /documents* /chat* /legal* /tasks* /entities* /search* /health* /plans* /memories* /tools* /mcp* /decisions* /manager* /preferences* /organizations* /learning* /cases* /vehicles* /admin* /facts* /categories* /appointments*
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/pytest tests/test_appointments.py -v`
Expected: PASS — all 7 tests green.

- [ ] **Step 7: Commit**

```bash
git add services/api/src/api/appointments.py services/api/src/api/main.py infra/caddy/Caddyfile services/api/tests/test_appointments.py
git commit -m "Add Appointments CRUD router (Phase 27b)"
```

---

## Task 3: `.ics` export endpoint

**Files:**
- Modify: `services/api/src/api/appointments.py`
- Test: `services/api/tests/test_appointments.py`

**Interfaces:**
- Consumes: `Appointment` model (Task 1), `router` (Task 2, same file).
- Produces: `GET /appointments/{id}/ics` returning `text/calendar` — consumed by Task 6's `downloadAppointmentIcs` frontend helper.

- [ ] **Step 1: Write the failing test**

Append to `services/api/tests/test_appointments.py`:

```python
async def test_export_ics_returns_well_formed_vevent(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post(
        "/appointments",
        headers=headers,
        json={"title": "APK inspection", "starts_at": "2026-07-14T09:30:00Z", "location": "RDW Keuringsstation, Arnhem"},
    )
    appointment_id = create.json()["id"]

    response = await client.get(f"/appointments/{appointment_id}/ics", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert 'filename="apk-inspection.ics"' in response.headers["content-disposition"]
    body = response.text
    assert "BEGIN:VEVENT" in body
    assert "SUMMARY:APK inspection" in body
    assert "LOCATION:RDW Keuringsstation\\, Arnhem" in body


async def test_export_ics_rejects_unknown_id(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        "/appointments/00000000-0000-0000-0000-000000000000/ics", headers=headers
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/pytest tests/test_appointments.py -v -k ics`
Expected: FAIL with 404 (no `/ics` route exists yet).

- [ ] **Step 3: Add the `.ics` endpoint**

Append to `services/api/src/api/appointments.py` (extend the existing `datetime`/`Response` imports at the top: change `from fastapi import APIRouter, Depends, HTTPException, Query, status` to `from fastapi import APIRouter, Depends, HTTPException, Query, Response, status`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/pytest tests/test_appointments.py -v`
Expected: PASS — all 9 tests green.

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/appointments.py services/api/tests/test_appointments.py
git commit -m "Add .ics export endpoint for appointments (Phase 27b)"
```

---

## Task 4: `lib/calendarGrid.ts` — pure date helpers

**Files:**
- Create: `apps/web/src/lib/calendarGrid.ts`
- Test: `apps/web/src/lib/calendarGrid.test.ts`

**Interfaces:**
- Produces: `toDateKey(date: Date): string`, `getMonthGridDates(year: number, month: number): Date[]`, `toDatetimeLocalValue(isoUtc: string): string`, `fromDatetimeLocalValue(value: string): string` — consumed by Task 5 (`CalendarGrid.tsx`) and Task 7 (`Calendar.tsx`).

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/lib/calendarGrid.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { fromDatetimeLocalValue, getMonthGridDates, toDateKey, toDatetimeLocalValue } from "./calendarGrid";

describe("toDateKey", () => {
  it("formats a date as YYYY-MM-DD in local time", () => {
    expect(toDateKey(new Date(2026, 6, 4))).toBe("2026-07-04");
  });
});

describe("getMonthGridDates", () => {
  it("returns 42 dates starting on the Monday on/before the 1st", () => {
    const dates = getMonthGridDates(2026, 6); // July 2026: the 1st is a Wednesday
    expect(dates).toHaveLength(42);
    expect(toDateKey(dates[0])).toBe("2026-06-29");
    expect(toDateKey(dates[41])).toBe("2026-08-09");
  });

  it("includes the 1st and last day of the target month", () => {
    const keys = getMonthGridDates(2026, 6).map(toDateKey);
    expect(keys).toContain("2026-07-01");
    expect(keys).toContain("2026-07-31");
  });
});

describe("toDatetimeLocalValue / fromDatetimeLocalValue", () => {
  it("round-trips a local date/time through the datetime-local string format", () => {
    const original = new Date(2026, 6, 14, 9, 30);
    const asLocalString = toDatetimeLocalValue(original.toISOString());
    expect(asLocalString).toBe("2026-07-14T09:30");
    const backToIso = fromDatetimeLocalValue(asLocalString);
    expect(new Date(backToIso).getTime()).toBe(original.getTime());
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && pnpm test -- --run src/lib/calendarGrid.test.ts`
Expected: FAIL — `Cannot find module './calendarGrid'`.

- [ ] **Step 3: Write the implementation**

Create `apps/web/src/lib/calendarGrid.ts`:

```ts
function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function toDateKey(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export function getMonthGridDates(year: number, month: number): Date[] {
  const firstOfMonth = new Date(year, month, 1);
  // JS getDay() is 0=Sun..6=Sat; shift so the grid starts on Monday.
  const firstWeekday = (firstOfMonth.getDay() + 6) % 7;
  const gridStart = new Date(year, month, 1 - firstWeekday);

  const dates: Date[] = [];
  for (let i = 0; i < 42; i++) {
    dates.push(new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i));
  }
  return dates;
}

export function toDatetimeLocalValue(isoUtc: string): string {
  const d = new Date(isoUtc);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

export function fromDatetimeLocalValue(value: string): string {
  return new Date(value).toISOString();
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/web && pnpm test -- --run src/lib/calendarGrid.test.ts`
Expected: PASS — all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/calendarGrid.ts apps/web/src/lib/calendarGrid.test.ts
git commit -m "Add pure month-grid date helpers for Calendar (Phase 27b)"
```

---

## Task 5: `components/ui/CalendarGrid.tsx` — month grid primitive

**Files:**
- Create: `apps/web/src/components/ui/CalendarGrid.tsx`
- Test: `apps/web/src/components/ui/CalendarGrid.test.tsx`

**Interfaces:**
- Consumes: `getMonthGridDates`, `toDateKey` (Task 4, `../../lib/calendarGrid`).
- Produces: `CalendarGrid` component, props `{ year: number; month: number; selectedDateKey: string; todayKey: string; appointmentDateKeys: Set<string>; onSelectDate: (dateKey: string) => void }` — consumed by Task 7 (`Calendar.tsx`).

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/components/ui/CalendarGrid.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CalendarGrid } from "./CalendarGrid";

describe("CalendarGrid", () => {
  it("renders 42 day cells including leading/trailing days from adjacent months", () => {
    render(
      <CalendarGrid
        year={2026}
        month={6}
        selectedDateKey="2026-07-14"
        todayKey="2026-07-14"
        appointmentDateKeys={new Set()}
        onSelectDate={() => {}}
      />,
    );
    expect(screen.getAllByRole("button")).toHaveLength(42);
  });

  it("marks today with a distinct style and the selected date as pressed", () => {
    render(
      <CalendarGrid
        year={2026}
        month={6}
        selectedDateKey="2026-07-20"
        todayKey="2026-07-14"
        appointmentDateKeys={new Set()}
        onSelectDate={() => {}}
      />,
    );
    expect(screen.getByLabelText("2026-07-14")).toHaveClass("border-accent");
    expect(screen.getByLabelText("2026-07-20")).toHaveAttribute("aria-pressed", "true");
  });

  it("shows a dot marker on days with at least one appointment", () => {
    render(
      <CalendarGrid
        year={2026}
        month={6}
        selectedDateKey="2026-07-14"
        todayKey="2026-07-14"
        appointmentDateKeys={new Set(["2026-07-14"])}
        onSelectDate={() => {}}
      />,
    );
    expect(screen.getByLabelText("2026-07-14").querySelector("span")).toBeInTheDocument();
    expect(screen.getByLabelText("2026-07-15").querySelector("span")).not.toBeInTheDocument();
  });

  it("calls onSelectDate with the clicked date's key", () => {
    const onSelectDate = vi.fn();
    render(
      <CalendarGrid
        year={2026}
        month={6}
        selectedDateKey="2026-07-14"
        todayKey="2026-07-14"
        appointmentDateKeys={new Set()}
        onSelectDate={onSelectDate}
      />,
    );
    fireEvent.click(screen.getByLabelText("2026-07-21"));
    expect(onSelectDate).toHaveBeenCalledWith("2026-07-21");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && pnpm test -- --run src/components/ui/CalendarGrid.test.tsx`
Expected: FAIL — `Cannot find module './CalendarGrid'`.

- [ ] **Step 3: Write the implementation**

Create `apps/web/src/components/ui/CalendarGrid.tsx`:

```tsx
import { getMonthGridDates, toDateKey } from "../../lib/calendarGrid";

export function CalendarGrid({
  year,
  month,
  selectedDateKey,
  todayKey,
  appointmentDateKeys,
  onSelectDate,
}: {
  year: number;
  month: number;
  selectedDateKey: string;
  todayKey: string;
  appointmentDateKeys: Set<string>;
  onSelectDate: (dateKey: string) => void;
}) {
  const dates = getMonthGridDates(year, month);

  return (
    <div role="grid" aria-label="Month calendar" className="grid grid-cols-7 gap-1">
      {dates.map((date) => {
        const key = toDateKey(date);
        const inMonth = date.getMonth() === month;
        const isToday = key === todayKey;
        const isSelected = key === selectedDateKey;
        const hasAppointments = appointmentDateKeys.has(key);
        return (
          <button
            key={key}
            type="button"
            aria-label={key}
            aria-pressed={isSelected}
            onClick={() => onSelectDate(key)}
            className={[
              "flex flex-col items-center gap-0.5 rounded-lg p-2 text-sm transition-colors",
              inMonth ? "text-ink" : "text-ink-3",
              isSelected ? "bg-accent text-white" : isToday ? "border border-accent" : "hover:bg-accent-soft",
            ].join(" ")}
          >
            {date.getDate()}
            {hasAppointments && <span aria-hidden="true" className="h-1 w-1 rounded-full bg-accent" />}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/web && pnpm test -- --run src/components/ui/CalendarGrid.test.tsx`
Expected: PASS — all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/ui/CalendarGrid.tsx apps/web/src/components/ui/CalendarGrid.test.tsx
git commit -m "Add CalendarGrid month-grid primitive (Phase 27b)"
```

---

## Task 6: `api.ts` additions — Appointment types, CRUD calls, `.ics` download

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Test: `apps/web/src/lib/api.test.ts`

**Interfaces:**
- Produces: `AppointmentOut` interface; `listAppointments`, `createAppointment`, `updateAppointment`, `deleteAppointment`, `downloadAppointmentIcs` functions (`apps/web/src/lib/api.ts`) — consumed by Task 7 (`Calendar.tsx`).

- [ ] **Step 1: Write the failing test**

Append to `apps/web/src/lib/api.test.ts` (add `downloadAppointmentIcs` to the existing import line at the top: `import { ApiError, approveEntity, clearToken, downloadAppointmentIcs, login, request, setToken } from "./api";`):

```ts
describe("downloadAppointmentIcs", () => {
  beforeEach(() => {
    clearToken();
    vi.stubGlobal("fetch", vi.fn());
    URL.createObjectURL = vi.fn(() => "blob:mock-url");
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches the ics endpoint with the auth header and triggers a download", async () => {
    setToken("secret-token");
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response("BEGIN:VCALENDAR", { status: 200 }));
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    await downloadAppointmentIcs("a1", "appointment.ics");

    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/appointments/a1/ics");
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer secret-token");
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");

    clickSpy.mockRestore();
  });

  it("throws ApiError on a non-ok response", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response("", { status: 404, statusText: "Not Found" }));

    await expect(downloadAppointmentIcs("missing", "x.ics")).rejects.toBeInstanceOf(ApiError);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm test -- --run src/lib/api.test.ts`
Expected: FAIL — `downloadAppointmentIcs` is not exported from `./api`.

- [ ] **Step 3: Add the appointment API functions**

Append to `apps/web/src/lib/api.ts` (after the `linkVehicleToCase` section, near the other domain-model blocks):

```ts
export interface AppointmentOut {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string | null;
  location: string | null;
  notes: string | null;
  case_id: string | null;
  vehicle_id: string | null;
  created_at: string;
}

export interface AppointmentInput {
  title: string;
  starts_at: string;
  ends_at?: string;
  location?: string;
  notes?: string;
}

export function listAppointments(from: string, to: string): Promise<AppointmentOut[]> {
  const params = new URLSearchParams({ from, to });
  return request<AppointmentOut[]>(`/appointments?${params}`);
}

export function createAppointment(input: AppointmentInput): Promise<AppointmentOut> {
  return request<AppointmentOut>("/appointments", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateAppointment(id: string, input: Partial<AppointmentInput>): Promise<AppointmentOut> {
  return request<AppointmentOut>(`/appointments/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteAppointment(id: string): Promise<void> {
  return request<void>(`/appointments/${id}`, { method: "DELETE" });
}

export async function downloadAppointmentIcs(id: string, filename: string): Promise<void> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_URL}/appointments/${id}/ics`, { headers });
  if (!response.ok) throw new ApiError(response.status, response.statusText);

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
```

`API_URL` is the module-private `const` already defined at the top of `api.ts` — no export needed since `downloadAppointmentIcs` lives in the same module.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && pnpm test -- --run src/lib/api.test.ts`
Expected: PASS — all tests green, including the 2 new `downloadAppointmentIcs` cases.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/api.test.ts
git commit -m "Add Appointment API client functions (Phase 27b)"
```

---

## Task 7: `Calendar.tsx` route — month grid + agenda pane, nav/routing/i18n

**Files:**
- Create: `apps/web/src/routes/Calendar.tsx`
- Modify: `apps/web/src/lib/navigation.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/locales/en.json`, `apps/web/src/locales/nl.json`, `apps/web/src/locales/de.json`
- Test: `apps/web/src/routes/Calendar.test.tsx`

**Interfaces:**
- Consumes: `CalendarGrid` (Task 5), `listAppointments`/`AppointmentOut`/`downloadAppointmentIcs` (Task 6), `toDateKey`/`getMonthGridDates` (Task 4), `Modal` (`../components/ui/Modal`).
- Produces: `Calendar` default export (`apps/web/src/routes/Calendar.tsx`) rendering the grid + read-only agenda pane — Task 8 adds create/edit/delete on top of this same file.

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/routes/Calendar.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Calendar from "./Calendar";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listAppointments: vi.fn(),
    createAppointment: vi.fn(),
    updateAppointment: vi.fn(),
    deleteAppointment: vi.fn(),
    downloadAppointmentIcs: vi.fn(),
  };
});

const JULY_APPOINTMENTS: api.AppointmentOut[] = [
  {
    id: "a1",
    title: "APK inspection",
    starts_at: "2026-07-14T09:30:00Z",
    ends_at: null,
    location: "RDW Keuringsstation, Arnhem",
    notes: "Bring the kenteken papers",
    case_id: null,
    vehicle_id: null,
    created_at: "2026-07-01T00:00:00Z",
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <Calendar />
    </MemoryRouter>,
  );
}

describe("Calendar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ toFake: ["Date"] }); // leave setTimeout real so waitFor/findBy* polling still works
    vi.setSystemTime(new Date(2026, 6, 14));
    vi.mocked(api.listAppointments).mockResolvedValue(JULY_APPOINTMENTS);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches appointments for the visible month grid range and renders the day count", async () => {
    renderPage();
    await waitFor(() => expect(api.listAppointments).toHaveBeenCalledWith("2026-06-29", "2026-08-09"));
    expect(screen.getAllByRole("button", { name: /2026-07-\d\d/ })).toHaveLength(31);
  });

  it("shows the selected day's appointments in the agenda pane, defaulting to today", async () => {
    renderPage();
    expect(await screen.findByText("APK inspection")).toBeInTheDocument();
    expect(screen.getByText("Bring the kenteken papers")).toBeInTheDocument();
  });

  it("updates the agenda pane when a different day is clicked", async () => {
    renderPage();
    await screen.findByText("APK inspection");
    fireEvent.click(screen.getByLabelText("2026-07-15"));
    await waitFor(() => expect(screen.queryByText("APK inspection")).not.toBeInTheDocument());
  });

  it("shows an Open in Maps link only when location is set", async () => {
    renderPage();
    await screen.findByText("APK inspection");
    expect(
      screen.getByRole("link", { name: /open in maps/i }),
    ).toHaveAttribute(
      "href",
      "https://www.google.com/maps/search/?api=1&query=RDW%20Keuringsstation%2C%20Arnhem",
    );
  });

  it("downloads the .ics file when the download button is clicked", async () => {
    renderPage();
    await screen.findByText("APK inspection");
    fireEvent.click(screen.getByRole("button", { name: /download .ics/i }));
    expect(api.downloadAppointmentIcs).toHaveBeenCalledWith("a1", "apk-inspection.ics");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && pnpm test -- --run src/routes/Calendar.test.tsx`
Expected: FAIL — `Cannot find module './Calendar'`.

- [ ] **Step 3: Add i18n keys**

In `apps/web/src/locales/en.json`, add a `nav.calendar` key inside the existing `"nav"` object and a new top-level `"calendar"` object:

```json
"calendar": {
  "title": "Calendar",
  "prevMonth": "Previous month",
  "nextMonth": "Next month",
  "newAppointment": "+ New appointment",
  "noAppointments": "No appointments on this day.",
  "openInMaps": "📍 Open in Maps",
  "downloadIcs": "⬇ Download .ics",
  "loadError": "Failed to load appointments"
}
```

(and `"calendar": "Calendar"` inside `"nav"`). Mirror the same two additions in `apps/web/src/locales/nl.json` (`"calendar": "Kalender"` in `nav`; `calendar.title: "Kalender"`, `prevMonth: "Vorige maand"`, `nextMonth: "Volgende maand"`, `newAppointment: "+ Nieuwe afspraak"`, `noAppointments: "Geen afspraken op deze dag."`, `openInMaps: "📍 Open in Maps"`, `downloadIcs: "⬇ Download .ics"`, `loadError: "Afspraken laden mislukt"`) and `apps/web/src/locales/de.json` (`"calendar": "Kalender"` in `nav`; `calendar.title: "Kalender"`, `prevMonth: "Vorheriger Monat"`, `nextMonth: "Nächster Monat"`, `newAppointment: "+ Neuer Termin"`, `noAppointments: "Keine Termine an diesem Tag."`, `openInMaps: "📍 In Maps öffnen"`, `downloadIcs: "⬇ .ics herunterladen"`, `loadError: "Termine konnten nicht geladen werden"`).

- [ ] **Step 4: Add the nav entry and route**

In `apps/web/src/lib/navigation.ts`, add `{ to: "/calendar", labelKey: "nav.calendar" }` to `NAV_ITEMS` (after the `/tasks` entry):

```ts
export const NAV_ITEMS: { to: string; labelKey: string }[] = [
  { to: "/", labelKey: "nav.dashboard" },
  { to: "/documents", labelKey: "nav.documents" },
  { to: "/chat", labelKey: "nav.aiChat" },
  { to: "/legal", labelKey: "nav.legalDraft" },
  { to: "/tasks", labelKey: "nav.tasks" },
  { to: "/calendar", labelKey: "nav.calendar" },
  { to: "/entities", labelKey: "nav.entities" },
  { to: "/cases", labelKey: "nav.cases" },
  { to: "/vehicles", labelKey: "nav.vehicles" },
  { to: "/assistant", labelKey: "nav.assistant" },
  { to: "/settings", labelKey: "nav.settings" },
];
```

In `apps/web/src/App.tsx`, add the import (after `import Tasks from "./routes/Tasks";`):

```tsx
import Calendar from "./routes/Calendar";
```

And the route (after the `/tasks` `<Route>` block, before `/entities`):

```tsx
<Route
  path="/calendar"
  element={
    <ProtectedRoute>
      <Calendar />
    </ProtectedRoute>
  }
/>
```

- [ ] **Step 5: Write `Calendar.tsx`**

Create `apps/web/src/routes/Calendar.tsx`:

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  downloadAppointmentIcs,
  listAppointments,
  type AppointmentOut,
} from "../lib/api";
import { getMonthGridDates, toDateKey } from "../lib/calendarGrid";
import { Button } from "../components/ui/Button";
import { CalendarGrid } from "../components/ui/CalendarGrid";

export default function Calendar() {
  const { t } = useTranslation();
  const today = useMemo(() => new Date(), []);
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selectedDateKey, setSelectedDateKey] = useState(toDateKey(today));
  const [appointments, setAppointments] = useState<AppointmentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const gridDates = useMemo(() => getMonthGridDates(year, month), [year, month]);
  const todayKey = toDateKey(today);

  const refresh = useCallback(() => {
    setLoading(true);
    const from = toDateKey(gridDates[0]);
    const to = toDateKey(gridDates[gridDates.length - 1]);
    listAppointments(from, to)
      .then(setAppointments)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("calendar.loadError")))
      .finally(() => setLoading(false));
  }, [gridDates, t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const appointmentDateKeys = useMemo(
    () => new Set(appointments.map((a) => toDateKey(new Date(a.starts_at)))),
    [appointments],
  );

  const dayAppointments = appointments
    .filter((a) => toDateKey(new Date(a.starts_at)) === selectedDateKey)
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at));

  function goToPrevMonth() {
    const prev = new Date(year, month - 1, 1);
    setYear(prev.getFullYear());
    setMonth(prev.getMonth());
  }

  function goToNextMonth() {
    const next = new Date(year, month + 1, 1);
    setYear(next.getFullYear());
    setMonth(next.getMonth());
  }

  async function handleDownloadIcs(appointment: AppointmentOut) {
    const slug = appointment.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "appointment";
    await downloadAppointmentIcs(appointment.id, `${slug}.ics`);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">{t("calendar.title")}</h1>
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" onClick={goToPrevMonth} aria-label={t("calendar.prevMonth")}>
            ‹
          </Button>
          <Button size="sm" variant="ghost" onClick={goToNextMonth} aria-label={t("calendar.nextMonth")}>
            ›
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      <div className="grid gap-4 md:grid-cols-[2fr,1fr]">
        {!loading && (
          <CalendarGrid
            year={year}
            month={month}
            selectedDateKey={selectedDateKey}
            todayKey={todayKey}
            appointmentDateKeys={appointmentDateKeys}
            onSelectDate={setSelectedDateKey}
          />
        )}

        <div className="flex flex-col gap-3 rounded-2xl border border-edge bg-surface p-4">
          {dayAppointments.length === 0 ? (
            <p className="text-sm text-ink-3">{t("calendar.noAppointments")}</p>
          ) : (
            dayAppointments.map((appointment) => (
              <div key={appointment.id} className="flex flex-col gap-1 border-b border-edge pb-3 last:border-0">
                <p className="text-sm font-medium text-ink">{appointment.title}</p>
                {appointment.notes && <p className="text-xs text-ink-2">{appointment.notes}</p>}
                <div className="mt-1 flex flex-wrap gap-2">
                  {appointment.location && (
                    <a
                      href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(appointment.location)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-accent hover:underline"
                    >
                      {t("calendar.openInMaps")}
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => handleDownloadIcs(appointment)}
                    className="text-xs text-accent hover:underline"
                  >
                    {t("calendar.downloadIcs")}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/web && pnpm test -- --run src/routes/Calendar.test.tsx`
Expected: PASS — all 5 tests green.

- [ ] **Step 7: Typecheck and full frontend suite**

Run: `cd apps/web && pnpm exec tsc -b && pnpm test -- --run`
Expected: no type errors; no regressions in any other route's tests.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/routes/Calendar.tsx apps/web/src/routes/Calendar.test.tsx apps/web/src/lib/navigation.ts apps/web/src/App.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "Add Calendar route: month grid + agenda pane (Phase 27b)"
```

---

## Task 8: Create/edit/delete modal

**Files:**
- Modify: `apps/web/src/routes/Calendar.tsx`
- Modify: `apps/web/src/locales/en.json`, `apps/web/src/locales/nl.json`, `apps/web/src/locales/de.json`
- Test: `apps/web/src/routes/Calendar.test.tsx`

**Interfaces:**
- Consumes: `Modal` (`../components/ui/Modal`), `createAppointment`/`updateAppointment`/`deleteAppointment` (Task 6), `toDatetimeLocalValue`/`fromDatetimeLocalValue` (Task 4).
- Produces: full create/edit/delete flow on the `Calendar` route — this is the final task before full-suite verification (Task 9).

- [ ] **Step 1: Write the failing tests**

Append to `apps/web/src/routes/Calendar.test.tsx`:

```tsx
describe("Calendar create/edit/delete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ toFake: ["Date"] }); // leave setTimeout real so waitFor/findBy* polling still works
    vi.setSystemTime(new Date(2026, 6, 14));
    vi.mocked(api.listAppointments).mockResolvedValue(JULY_APPOINTMENTS);
    vi.mocked(api.createAppointment).mockResolvedValue({ ...JULY_APPOINTMENTS[0], id: "a2", title: "New one" });
    vi.mocked(api.updateAppointment).mockResolvedValue({ ...JULY_APPOINTMENTS[0], title: "Edited" });
    vi.mocked(api.deleteAppointment).mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("opens the create modal, submits, and calls createAppointment", async () => {
    renderPage();
    await screen.findByText("APK inspection");

    fireEvent.click(screen.getByRole("button", { name: /new appointment/i }));
    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: "New one" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(api.createAppointment).toHaveBeenCalled());
    const [payload] = vi.mocked(api.createAppointment).mock.calls[0];
    expect(payload.title).toBe("New one");
  });

  it("opens the edit modal pre-filled when an agenda item is clicked, and calls updateAppointment on submit", async () => {
    renderPage();
    await screen.findByText("APK inspection");

    fireEvent.click(screen.getByText("APK inspection"));
    const titleInput = screen.getByLabelText(/title/i) as HTMLInputElement;
    expect(titleInput.value).toBe("APK inspection");

    fireEvent.change(titleInput, { target: { value: "Edited" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(api.updateAppointment).toHaveBeenCalledWith("a1", expect.objectContaining({ title: "Edited" })));
  });

  it("deletes an appointment via the confirm modal", async () => {
    renderPage();
    await screen.findByText("APK inspection");

    fireEvent.click(screen.getByText("APK inspection"));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete appointment" }));

    await waitFor(() => expect(api.deleteAppointment).toHaveBeenCalledWith("a1"));
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && pnpm test -- --run src/routes/Calendar.test.tsx`
Expected: FAIL — no "New appointment" button, no title input, no delete button exist yet.

- [ ] **Step 3: Add i18n keys for the form**

Add to `apps/web/src/locales/en.json`'s `"calendar"` object: `"titleLabel": "Title"`, `"startsAtLabel": "Starts at"`, `"locationLabel": "Location"`, `"notesLabel": "Notes"`, `"deleteModalTitle": "Delete this appointment?"`, `"deleteModalBody": "This can't be undone."`, `"deleteConfirm": "Delete appointment"`, `"createError": "Failed to save appointment"`, `"deleteError": "Failed to delete appointment"`. Note `deleteConfirm` is deliberately *not* just "Delete" — the edit modal's trigger button (`common.delete`) already renders "Delete", and both buttons are mounted simultaneously once the confirm modal opens (nested-modal pattern, not `DocumentDetail.tsx`'s single-modal-on-base-page one), so identical text would make them ambiguous both to screen readers and to `getByRole` in tests — same reasoning behind `documentDetail.deleteConfirm`'s existing "Delete document" wording. Mirror with Dutch (`"Titel"`, `"Begintijd"`, `"Locatie"`, `"Notities"`, `"Afspraak verwijderen?"`, `"Dit kan niet ongedaan worden gemaakt."`, `"Afspraak verwijderen"`, `"Opslaan van afspraak mislukt"`, `"Verwijderen van afspraak mislukt"`) and German (`"Titel"`, `"Beginnt um"`, `"Ort"`, `"Notizen"`, `"Diesen Termin löschen?"`, `"Dies kann nicht rückgängig gemacht werden."`, `"Termin löschen"`, `"Termin konnte nicht gespeichert werden"`, `"Termin konnte nicht gelöscht werden"`) in `nl.json`/`de.json` respectively.

- [ ] **Step 4: Add the modal to `Calendar.tsx`**

In `apps/web/src/routes/Calendar.tsx`, update the imports:

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  createAppointment,
  deleteAppointment,
  downloadAppointmentIcs,
  listAppointments,
  updateAppointment,
  type AppointmentOut,
} from "../lib/api";
import { fromDatetimeLocalValue, getMonthGridDates, toDateKey, toDatetimeLocalValue } from "../lib/calendarGrid";
import { Button } from "../components/ui/Button";
import { CalendarGrid } from "../components/ui/CalendarGrid";
import { Modal } from "../components/ui/Modal";
```

Add state and handlers inside the component (after the existing `dayAppointments` computation):

```tsx
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<AppointmentOut | null>(null);
  const [formTitle, setFormTitle] = useState("");
  const [formStartsAt, setFormStartsAt] = useState("");
  const [formLocation, setFormLocation] = useState("");
  const [formNotes, setFormNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  function openCreateForm() {
    setEditing(null);
    setFormTitle("");
    setFormStartsAt(`${selectedDateKey}T09:00`);
    setFormLocation("");
    setFormNotes("");
    setFormOpen(true);
  }

  function openEditForm(appointment: AppointmentOut) {
    setEditing(appointment);
    setFormTitle(appointment.title);
    setFormStartsAt(toDatetimeLocalValue(appointment.starts_at));
    setFormLocation(appointment.location ?? "");
    setFormNotes(appointment.notes ?? "");
    setFormOpen(true);
  }

  async function handleSubmitForm() {
    if (!formTitle.trim() || !formStartsAt) return;
    setSaving(true);
    try {
      const payload = {
        title: formTitle.trim(),
        starts_at: fromDatetimeLocalValue(formStartsAt),
        location: formLocation.trim() || undefined,
        notes: formNotes.trim() || undefined,
      };
      if (editing) {
        await updateAppointment(editing.id, payload);
      } else {
        await createAppointment(payload);
      }
      setFormOpen(false);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("calendar.createError"));
    } finally {
      setSaving(false);
    }
  }

  async function handleConfirmDelete() {
    if (!editing) return;
    setDeleting(true);
    try {
      await deleteAppointment(editing.id);
      setConfirmDeleteOpen(false);
      setFormOpen(false);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("calendar.deleteError"));
    } finally {
      setDeleting(false);
    }
  }
```

Add the "New appointment" button next to the month-nav buttons in the header `<div>`:

```tsx
          <Button size="sm" variant="secondary" onClick={openCreateForm}>
            {t("calendar.newAppointment")}
          </Button>
```

Make each agenda item clickable to open the edit form — wrap the existing per-appointment `<div>` content's title in a clickable element:

```tsx
                <button type="button" onClick={() => openEditForm(appointment)} className="text-left text-sm font-medium text-ink hover:underline">
                  {appointment.title}
                </button>
```

(replacing the plain `<p className="text-sm font-medium text-ink">{appointment.title}</p>` from Task 7).

Add the form modal and confirm-delete modal at the end of the returned JSX, just before the closing `</div>` of the root element:

```tsx
      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? editing.title : t("calendar.newAppointment")}>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-2" htmlFor="appointment-title">
              {t("calendar.titleLabel")}
            </label>
            <input
              id="appointment-title"
              type="text"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-2" htmlFor="appointment-starts-at">
              {t("calendar.startsAtLabel")}
            </label>
            <input
              id="appointment-starts-at"
              type="datetime-local"
              value={formStartsAt}
              onChange={(e) => setFormStartsAt(e.target.value)}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-2" htmlFor="appointment-location">
              {t("calendar.locationLabel")}
            </label>
            <input
              id="appointment-location"
              type="text"
              value={formLocation}
              onChange={(e) => setFormLocation(e.target.value)}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-2" htmlFor="appointment-notes">
              {t("calendar.notesLabel")}
            </label>
            <textarea
              id="appointment-notes"
              value={formNotes}
              onChange={(e) => setFormNotes(e.target.value)}
              className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>
          <div className="flex justify-between gap-2">
            {editing && (
              <Button variant="danger" size="sm" onClick={() => setConfirmDeleteOpen(true)}>
                {t("common.delete")}
              </Button>
            )}
            <div className="ml-auto flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => setFormOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button size="sm" variant="primary" onClick={handleSubmitForm} disabled={saving || !formTitle.trim()}>
                {t("common.create")}
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal open={confirmDeleteOpen} onClose={() => setConfirmDeleteOpen(false)} title={t("calendar.deleteModalTitle")}>
        <p className="mb-4 text-sm text-ink-2">{t("calendar.deleteModalBody")}</p>
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={() => setConfirmDeleteOpen(false)}>
            {t("common.cancel")}
          </Button>
          <Button variant="danger" size="sm" onClick={handleConfirmDelete} disabled={deleting}>
            {t("calendar.deleteConfirm")}
          </Button>
        </div>
      </Modal>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/web && pnpm test -- --run src/routes/Calendar.test.tsx`
Expected: PASS — all 8 tests green (5 from Task 7 + 3 new).

- [ ] **Step 6: Typecheck and full frontend suite**

Run: `cd apps/web && pnpm exec tsc -b && pnpm test -- --run`
Expected: no type errors; no regressions elsewhere.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/routes/Calendar.tsx apps/web/src/routes/Calendar.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "Add create/edit/delete modal to Calendar (Phase 27b)"
```

---

## Task 9: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite against the local Postgres**

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/pytest -q`
Expected: all `test_appointments.py` tests pass; compare the total failure count against this project's documented pre-existing baseline before concluding any *other* file's failure is a regression introduced here (this plan's changes only touch `models.py`, `main.py`, and add new files — no existing router logic is modified).

- [ ] **Step 2: Run the full frontend suite and typecheck**

Run: `cd apps/web && pnpm exec tsc -b && pnpm test -- --run`
Expected: 0 failures, 0 type errors.

- [ ] **Step 3: Stop the local Postgres test instance**

```bash
/usr/local/bin/pg_ctl -D /Users/stagnaat/.claude/jobs/2ca9e950/tmp/pgdata stop
```

- [ ] **Step 4: Manual smoke check (if a browser session is available)**

Navigate to `/calendar`, confirm the current month renders with today highlighted, click a day with the seeded appointment, confirm the agenda pane shows it with a working "Open in Maps" link and a `.ics` download that produces a file a real calendar app can import, create a new appointment via the modal and confirm it appears on the right day after refresh, and confirm the delete flow removes it.
