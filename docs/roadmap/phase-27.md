# Phase 27 — Kanban board (Tasks) + Calendar (Appointments)

> **Status: 27a done, 27b not started.** 27a (Kanban board) is built and
> deployed — `Task.position`, the `in_progress` status, and the
> `KanbanBoard` component, ADR 0045. 27b (Calendar/Appointments) is still
> just the spec below. Written before code per the discipline
> `docs/roadmap/README.md` asks for: goal, why now, open design questions,
> and a smallest-safe-slice scope cut, before touching the database.

## Goal

Two independent, separately-shippable slices:

- **27a — Kanban board**: turn the existing `/tasks` list page into a
  drag-and-drop board with `todo` / `progress` / `done` columns, matching
  the artifact's `.kanban` pattern (lines 480-489, 908-921 of the design
  doc).
- **27b — Calendar**: a new `/calendar` page — month grid + agenda pane for
  the selected day, matching the artifact's `.cal-shell` pattern (lines
  555-579, 1007-1018), backed by a new `Appointment` model.

## Why now

Both were cataloged in the design-language artifact and explicitly flagged
as deferred, backend-requiring work in ADR 0044 rather than attempted
silently in that pass. The user asked to scope them next.

## What already exists (don't rebuild)

- `Task` model (`services/api/src/api/models.py:164`) — `id`, `document_id`,
  `title`, `description`, `due_date` (date, not datetime), `assignee`
  (free text), `status` (currently only `"open"`/`"done"`), `source`,
  `created_by`, `created_at`. Deliberately minimal per ADR 0004.
- `GET/PATCH /tasks` (`services/api/src/api/tasks.py`) — list with
  `status`/`document_id` filters, single-field status PATCH.
- `Tasks.tsx` — list view with open/done/all filter tabs, works, has
  passing tests. **Not being replaced** — becomes a view-toggle sibling to
  the new board, so due-date/assignee/source-document display and the
  existing filter UX aren't regressed.
- Case↔Task linking already exists via the polymorphic `GraphEdge` table
  (Phase 10, ADR 0025), not a new FK — reuse this for any case-scoped task
  filtering, don't add `case_id` to `Task`.
- No `organization_id` on `Task`/`Case` — per-table tenant isolation is a
  deliberately deferred Phase 14 follow-up (ADR 0029), not a design gap in
  this phase. New tables here (none for 27a; `Appointment` for 27b) follow
  the same convention: no `organization_id`, globally visible to all
  authenticated users, same as `Task`/`Case` today.
- No file-download endpoint pattern exists yet anywhere in the API — 27b's
  `.ics` export is a first, using FastAPI's plain `Response(media_type=...)`,
  no new dependency (no `icalendar` package needed for one `VEVENT`).

## Open design questions (resolved here, flag if wrong)

1. **Does "Kanban" replace the Tasks list, or sit alongside it?**
   → Alongside. Add a List/Board toggle to `Tasks.tsx`. Backend list
   endpoint is unchanged either way.
2. **Third status value — name it what?**
   → Add `"in_progress"`. Existing `"open"` stays the "todo" column,
   `"done"` stays "done" — avoids a disruptive rename/backfill of existing
   task rows. The `PATCH /tasks/{id}` status whitelist
   (`tasks.py:76`, currently `("open", "done")`) becomes
   `("open", "in_progress", "done")`.
3. **How does drag-and-drop persist card order within a column?**
   → New `position: int` column on `Task`, NOT NULL, backfilled by
   `created_at` order within each status group at migration time. A move
   (drag to new column and/or new position) is one `PATCH /tasks/{id}`
   call carrying `{status, position}`; the endpoint re-sequences the
   affected column(s) server-side (small N per board — no sparse/float
   positioning scheme needed at this scale).
4. **Is "Deadlines & Reminders" (artifact lines 523-553, the countdown
   hero + checkable reminder rows + repeat-cadence add form) in scope?**
   → **No, explicitly deferred.** It's visually adjacent to the calendar
   in the artifact but wasn't part of the ask. It also implies real scope
   of its own the artifact doesn't need for this phase: recurrence
   ("repeat cadence"), the notification-bell unread-count wiring
   (artifact lines 596-603), and a delivery mechanism (push/email/Signal)
   for the reminder to mean anything beyond a checkbox. `Task.due_date`
   already covers "a thing with a due date I can check off" for anyone
   who wants that today via the existing Tasks page. Revisit as its own
   phase if wanted.
5. **Appointment vs. Task — why a new model instead of extending Task?**
   → `Task.due_date` is `Date`, not `DateTime` — appointments need
   time-of-day. Appointments also need `location` (for the artifact's
   "Open in Maps" link) and no `status`/`done` concept (an appointment
   isn't completed, it happens or doesn't). Overloading `Task` with
   nullable time/location fields that only apply to some rows is worse
   than a small, separate table.
6. **"Open in Maps" — real Maps API, or a plain link?**
   → Plain link, no API key: `https://www.google.com/maps/search/?api=1&query=<url-encoded location>`.
   No geocoding, no embedded map widget. If `location` is empty, don't
   render the link.

## 27a — Kanban board

### Migration

New revision, `down_revision` = `c8f2a5e9d3b7` (Phase 26, current head):

```python
def upgrade() -> None:
    op.add_column("tasks", sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
    op.execute("""
        UPDATE tasks SET position = sub.rn - 1
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY status ORDER BY created_at) AS rn
            FROM tasks
        ) AS sub
        WHERE tasks.id = sub.id
    """)
    op.alter_column("tasks", "position", server_default=None)

def downgrade() -> None:
    op.drop_column("tasks", "position")
```

### Backend (`services/api/src/api/tasks.py`)

- `TaskOut` gains `position: int`.
- `TaskUpdate` gains `position: int | None = None`.
- `update_task`: whitelist becomes `("open", "in_progress", "done")`. If
  `update.position is not None`, re-sequence: shift every other task in
  the *target* status column with `position >= update.position` up by one
  (simple `UPDATE ... WHERE status = :s AND position >= :p` before
  assigning the moved task's new position), so no two tasks in the same
  column ever collide. If status changed and position was omitted, append
  to the end of the new column (`max(position) + 1`, or `0` if empty).
- `list_tasks`: add `.order_by(Task.status, Task.position)` (currently
  orders by `created_at.desc()` only — fine for the list view, wrong for
  a stable board layout).

### Frontend

- New `apps/web/src/components/ui/KanbanBoard.tsx` — three
  `.kanban-col`-style columns (`todo`/`in_progress`/`done`), native HTML5
  drag-and-drop (`draggable`, `onDragStart`, `onDragOver`, `onDrop`)
  matching the artifact's classes/interaction, not a new drag library.
  Props: `tasks: TaskOut[]`, `onMove: (taskId: string, status: string, position: number) => void`.
- `Tasks.tsx`: add a List/Board toggle (reuse the existing filter-tab
  `Button` pattern); Board mode ignores the open/done/all filter tabs
  (shows all three columns) and renders `KanbanBoard`.
- `lib/api.ts`: extend `updateTaskStatus` (or add `moveTask`) to send
  `{status, position}`.

### Tests

- Backend: migration backfill correctness (positions are 0..N-1 per
  status group, no gaps assumed by callers); `PATCH` rejects unknown
  status; `PATCH` with a position collision correctly shifts siblings;
  `list_tasks` ordering.
- Frontend: `KanbanBoard.test.tsx` — renders three columns with correct
  cards, `fireEvent.drop` on a column calls `onMove` with the right
  args; `Tasks.test.tsx` — toggle switches between list and board.

## 27b — Calendar (Appointments)

### New model (`services/api/src/api/models.py`)

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
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Index on `starts_at` (month-range queries are the only access pattern).

### Migration

New revision, chained after 27a's: adds `appointments` table + index on
`starts_at`.

### Backend (`services/api/src/api/appointments.py`, new)

- `POST /appointments` — create.
- `GET /appointments?from=&to=` — list within an inclusive date range
  (both required; the frontend always asks for a visible month), ordered
  by `starts_at`. No user-scoping, same convention as `list_tasks`.
- `PATCH /appointments/{id}` — edit any field.
- `DELETE /appointments/{id}`.
- `GET /appointments/{id}/ics` — hand-rolled single-`VEVENT` `.ics` text
  via `Response(content=..., media_type="text/calendar", headers={"Content-Disposition": f'attachment; filename="{slug}.ics"'})`.
  No new dependency.
- Register in `main.py`, add `/appointments*` to `infra/caddy/Caddyfile`'s
  `@api` matcher (same step missed-then-fixed twice before — ADR 0039/0043
  — do it in the same commit as the router this time).

### Frontend

- New `apps/web/src/routes/Calendar.tsx` — `.cal-card` month grid (7-col,
  today/selected/has-event states, `ev-dot` marker) + `.agenda-card` for
  the selected day, matching artifact structure. Fetches
  `GET /appointments?from=<month start>&to=<month end>` on month change.
  Agenda item shows time, title, notes, and (if `location` set) an "Open
  in Maps" link + a "Download .ics" button hitting the new endpoint
  directly (`<a href="/appointments/{id}/ics" download>`, no JS fetch
  needed for a same-origin authenticated download via cookie/header — 
  confirm the API's auth is cookie-based before relying on a bare `<a>`;
  if it's bearer-token-in-header only, this needs a `fetch` + blob-URL
  download instead).
- New primitive `apps/web/src/components/ui/Calendar.tsx` if the month
  grid logic is reusable enough to extract from `Calendar.tsx` the route
  — otherwise keep it inline in the route; decide during implementation,
  don't speculate now.
- Add `{ to: "/calendar", label: "Calendar" }` to
  `apps/web/src/lib/navigation.ts:NAV_ITEMS` and a route in `App.tsx`
  alongside the other authenticated routes.

### Tests

- Backend: create/list-by-range/edit/delete round-trip; `.ics` endpoint
  returns `text/calendar` with a well-formed `VEVENT` (parseable, not
  necessarily via a library — a regex/substring check on required fields
  is enough); Caddy path-matcher regression guarded by re-checking the
  full `@api` list, not just appending (this project has broken this
  twice already).
- Frontend: `Calendar.test.tsx` — month grid renders correct day count
  and today/selected states, clicking a day updates the agenda pane,
  "Open in Maps" link only renders when `location` is set.

## Acceptance criteria

- **27a**: `/tasks` has a working Board view with 3 columns; drag a card
  to a new column or position, reload the page, order and column persist.
  Existing List view and its tests are unchanged and still pass.
- **27b**: `/calendar` renders the current month, shows event dots on
  days with appointments, clicking a day shows its agenda, creating an
  appointment (via a form — reuse the `Modal` primitive) appears on the
  right day after refresh, downloading `.ics` produces a file a real
  calendar app can import.
- Full test suite (backend + frontend) green against the pre-existing
  baseline (14 known pre-existing backend failures, 0 frontend failures),
  same verification discipline as every phase before this one.

## Explicitly out of scope for Phase 27

- Deadlines & Reminders section (countdown hero, repeat cadence,
  notification-bell badge) — see open question 4.
- Recurring appointments (weekly/monthly repeat).
- A dedicated per-case Kanban board (only the global `/tasks` board).
- Real Maps API integration (geocoding, embedded map, distance/ETA).
- `.ics` *import* (only export).
- Any push/email/Signal notification tied to an approaching appointment
  or deadline — this needs its own delivery-infrastructure phase.
