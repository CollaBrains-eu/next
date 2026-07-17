# Phase 27b — Calendar (Appointments) Design

> **2026-07-17 update:** re-confirmed via a fresh brainstorming pass
> (P3 of ADR 0063) — this spec was still accurate against current code
> (UUID ids, bearer-token auth, Caddyfile gap all re-verified) and is
> adopted as-is, plus one addition: an optional `vehicle_id` FK. The
> artifact's own mock data ties an appointment to a vehicle
> (`title:'RDW appointment — 2-KTD-80'`), so "case/entity-linkable"
> means both, not just `case_id`. Recurrence and proactive
> notifications were re-confirmed out of scope for v1.

**Goal:** A `/calendar` page — month grid + agenda pane, backed by a new
`Appointment` model — with full create/edit/delete in the UI and a
per-event `.ics` export, matching the design-language artifact's
`.cal-shell` pattern.

**Architecture:** New `Appointment` table (separate from `Task`, since
appointments need time-of-day and a location, which `Task.due_date`
doesn't have). A new `appointments.py` router with standard CRUD plus a
hand-rolled `.ics` export endpoint. A new `Calendar.tsx` route rendering
a month grid and an agenda pane for the selected day, with a `Modal`-based
form for create/edit and a second confirm-`Modal` for delete — the same
pattern already used by `DocumentDetail.tsx`.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic (backend),
React + Vite + TypeScript + Tailwind, existing `Modal` primitive
(frontend). No new dependencies (no `icalendar` package — a single
`VEVENT` is hand-rolled text).

## Global Constraints

- No `organization_id` on `Appointment` — matches every other table's
  current convention (per-table tenant isolation is a deferred Phase 14
  follow-up, ADR 0029). Global visibility to all authenticated users,
  same as `Task`/`Case` today.
- `GET /appointments` requires both `from` and `to` (the frontend always
  asks for a visible month's range — no unbounded list).
- Auth is bearer-token-in-`localStorage` (`apps/web/src/lib/api.ts`),
  not cookies — the `.ics` download must go through `fetch` + a blob URL,
  not a bare `<a href download>`, or the request won't carry the
  `Authorization` header.
- Caddy's `@api` path matcher in `infra/caddy/Caddyfile` must get
  `/appointments*` added in the same commit as the router — this exact
  step has been missed and had to be fixed after the fact twice already
  in this project (ADR 0039, ADR 0043).
- Full test-suite verification (isolated throwaway-container run against
  the live DB for backend; `pnpm vitest run` in the live `web` container
  for frontend) gates deploy, same discipline as every phase before this
  one. Current known pre-existing backend baseline: 14 failures across
  `test_ai_gateway`, `test_chat` (x2), `test_documents` (x3),
  `test_entities` (x7) — any run should match this exactly, no more, no
  fewer.

---

## Data model

```python
class Appointment(Base):
    """A scheduled event with a specific time (unlike Task.due_date, which
    is date-only) and an optional physical location, for the calendar/
    agenda page and .ics export.
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

Migration: new revision, `down_revision = 'd1a4e7f9c2b6'` (27a's head).
Creates the `appointments` table plus an index on `starts_at`.

`case_id` and `vehicle_id` exist on the model and are accepted by the
API, but the v1 UI has no case/vehicle picker — same "field exists, UI
doesn't surface it yet" choice already made for `Task`/Kanban in 27a.

## Backend API (`services/api/src/api/appointments.py`, new)

- `POST /appointments` — create. Body: `title`, `starts_at` (required);
  `ends_at`, `location`, `notes`, `case_id`, `vehicle_id` (optional).
- `GET /appointments?from=<date>&to=<date>` — both required, inclusive
  range, ordered by `starts_at`. No pagination — a month's worth of
  appointments is small.
- `PATCH /appointments/{id}` — edit any field, partial update.
- `DELETE /appointments/{id}` — hard delete, `204`.
- `GET /appointments/{id}/ics` — returns:
  ```python
  Response(
      content=ics_text,
      media_type="text/calendar",
      headers={"Content-Disposition": f'attachment; filename="{slug}.ics"'},
  )
  ```
  where `ics_text` is a minimal, hand-built `VCALENDAR`/`VEVENT` block
  (`UID`, `DTSTART`, `DTEND` if set, `SUMMARY`, `LOCATION` if set,
  `DESCRIPTION` if `notes` set). No `icalendar` dependency.
- Register in `main.py`; add `/appointments*` to the Caddyfile's `@api`
  matcher in the same commit.

## Frontend: Calendar page (`routes/Calendar.tsx`, new)

- Month grid (7 columns, Mon–Sun), computed client-side from the
  currently-viewed month (prev/next month nav buttons). Today and the
  selected day get distinct visual states; days with ≥1 appointment get
  a small dot marker.
- Fetches `GET /appointments?from=&to=` covering the full visible grid
  (including the leading/trailing days from adjacent months that fill
  out the grid) whenever the viewed month changes.
- Agenda pane shows the selected day's appointments, sorted by
  `starts_at`: time, title, notes, an "Open in Maps" link
  (`https://www.google.com/maps/search/?api=1&query=<url-encoded location>`,
  only rendered when `location` is set — no geocoding, no API key), and
  a "Download .ics" button.
- "New appointment" button opens the create/edit `Modal` (see below),
  defaulting `starts_at` to the selected day.
- Clicking an existing agenda item opens the same `Modal`, pre-filled,
  in edit mode.
- Nav entry: `{ to: "/calendar", label: "Calendar" }` added to
  `apps/web/src/lib/navigation.ts`; route added in `App.tsx` alongside
  the other authenticated routes.

## Frontend: Create/Edit/Delete modal

- One `Modal`-based form component, used for both create and edit
  (edit mode is "create, pre-filled, with a Delete button and a PATCH
  instead of POST on submit"). Fields: title (text), starts_at
  (datetime-local input), ends_at (datetime-local input, optional),
  location (text, optional), notes (textarea, optional).
- Timezone handling: `<input type="datetime-local">` produces a
  timezone-naive value in the browser's local time. Convert it to a
  `Date` and send its ISO string (`.toISOString()`, UTC) to the API;
  when pre-filling the edit form, convert the API's UTC timestamp back
  to a local-time `datetime-local` string. The backend only ever
  stores/returns UTC — no server-side timezone logic needed.
- Delete is a button inside the edit modal; clicking it opens a second,
  small confirm `Modal` ("Delete this appointment?" / Cancel / Delete) —
  the same two-modal pattern `DocumentDetail.tsx` already uses for its
  delete flow, not a new pattern.
- On successful create/edit/delete, refetch the visible month's range
  and close the modal.
- `.ics` download: `fetch("/appointments/{id}/ics", { headers: { Authorization: ... } })`
  → read the response as a `Blob` → create an object URL → trigger a
  synthetic `<a>` click → revoke the object URL. (Bare `<a href download>`
  won't carry the bearer token, per the Global Constraints section.)

## Testing plan

**Backend** (`services/api/tests/test_appointments.py`, new):
- Create → appears in a `GET` covering its date range.
- `GET` excludes appointments outside the requested range.
- `PATCH` updates fields; `DELETE` removes it and a subsequent `GET`
  no longer includes it.
- `.ics` endpoint: response `media_type` is `text/calendar`; body
  contains `BEGIN:VEVENT`, a `SUMMARY:` line matching the title, and
  (when set) a `LOCATION:` line — checked via substring/regex, no new
  parsing dependency.
- Auth: all endpoints reject a missing token with `401`.

**Frontend** (`Calendar.test.tsx`, new):
- Renders the correct number of day cells for a given month and marks
  today/selected correctly.
- Clicking a day updates the agenda pane to that day's appointments.
- Submitting the create form calls the create API and the new
  appointment shows up after refetch.
- Clicking an agenda item opens the modal pre-filled with its data;
  submitting calls the edit API.
- Delete flow: clicking Delete opens the confirm modal; confirming
  calls the delete API.
- "Open in Maps" link is present only when `location` is set.
- Clicking "Download .ics" triggers a `fetch` to the right URL (verify
  via a mocked `fetch`, not an actual file-save assertion).

## Explicitly out of scope (unchanged from `docs/roadmap/phase-27.md`)

- Deadlines & Reminders section (countdown hero, repeat cadence,
  notification-bell badge wiring) — its own phase if wanted.
- Recurring appointments (weekly/monthly repeat).
- Real Maps API integration (geocoding, embedded map, distance/ETA).
- `.ics` *import* (export only).
- Any push/email/Signal notification tied to an approaching appointment.
- A case picker in the create/edit UI (the `case_id` field exists on the
  model and API but isn't surfaced in the v1 form).
