# Calendar Auto-Sync — Design Spec

**Sub-project 3b of the CollaBrains premium-SaaS redesign** (metafields + document UI
already shipped; this is next in the Documents-redesign sequence, before address
consolidation). Addresses the remaining part of the user's original ask: "(even in
sync with calendar)" — extracted, appointment-like tasks should end up on the
calendar without a manual step.

## Background

Research into the current codebase found:

- `Task.category` (`payment`/`appointment`/`deadline`/`notification`,
  `tasks.py:27`) is **manual-only** today — the only place it's ever set is
  `update_task`'s `PATCH /tasks/{id}` handler (`tasks.py:259`). Task extraction
  (`planner_agent.py::extract_tasks`) never sets it. So no document today produces
  an `appointment`-category task on its own.
- `Appointment` (`models.py:674-697`) is a fully CRUD'd, calendar/`.ics`-capable model,
  but is 100% manually created — no code path ever constructs one automatically.
  `planner_agent.py`'s own module docstring documents this as a deliberate original
  scope decision (ADR 0004): "Deliberately narrow scope -- task extraction, not
  scheduling... out of scope (calendar sync, recurrence, real user assignment)." This
  spec deliberately walks back the calendar-sync part of that deferral, the same way
  ADR 0064 already walked back the recurrence/notifications part (per `Task`'s own
  updated docstring).
- v2's own "calendar sync" was stateless .ics generation from extracted appointment
  action items, never persisted. Current already has a *better* foundation (a real,
  persisted, editable `Appointment` model) — this spec connects that foundation to
  extraction, rather than reverting to v2's stateless approach.

## Scope

**In scope:**
1. Automatic task categorization as part of the existing extraction call.
2. Automatic `Appointment` creation for any task that ends up with
   `category == "appointment"` and a `due_date`, from any of the three places a
   task's category can be set (auto-extraction, manual creation, manual update).
3. A nullable `Appointment.source_task_id` link back to its originating task.

**Out of scope:**
- Bidirectional sync — editing or deleting a `Task` after its `Appointment` was
  created does not touch the `Appointment`. The `Appointment` becomes independently
  editable via existing CRUD once created.
- Location — `Task` has no location field, so auto-created appointments have
  `location=null` until a user edits them.
- A "linked from task" UI badge — nice-to-have, not required for this spec.
- Address consolidation (still deferred, lowest priority, per the prior sequencing
  decision — current's address model already exceeds v2's).

## Architecture

### 1. Task auto-categorization

Extends `planner_agent.py`'s existing single `chat_completion` call (not a new,
separate LLM round-trip) — category is a natural per-item property of the same
extraction, unlike document metafields/classification which stayed split for
auditability of otherwise-unrelated concerns.

`EXTRACTION_PROMPT` gains a `"category"` field per item: one of
`payment|appointment|deadline|notification`, or `null` if none clearly applies.
`EXTRACTION_SCHEMA` gains the matching enum property. `extract_tasks` sets
`task.category` from the parsed response (defaulting to `None` on an invalid/missing
value, same graceful-degradation posture as every other extraction module here).

`TASK_CATEGORIES` moves from `tasks.py` to `models.py` (a plain module-level tuple,
near the `Task` class) so both `tasks.py` and `planner_agent.py` can import it —
`tasks.py` already imports from `planner_agent.py`, so the reverse import would be
circular.

### 2. Appointment auto-creation

New module `calendar_sync.py`, following the codebase's established pattern of small,
single-purpose modules:

```python
async def sync_appointment_for_task(db: AsyncSession, *, task: Task, user_id: UUID | None) -> Appointment | None
```

Creates and returns a new `Appointment` when `task.category == "appointment"` and
`task.due_date is not None` and `user_id is not None` (guards the rare case a caller
has no user in scope) and no `Appointment` with `source_task_id == task.id` already
exists (dedup — needed because `update_task` can be called repeatedly). Returns
`None` (no-op) otherwise. The created `Appointment` gets:

- `title = task.title`
- `starts_at` = midnight UTC of `task.due_date` (all-day, matching the same
  all-day convention `tasks.py`'s own `.ics` export already uses for `due_date`)
- `ends_at = None`, `location = None`
- `notes = task.description`
- `created_by = user_id`
- `source_task_id = task.id`

Hooked into three call sites, each already committing the `Task` change:

- `planner_agent.py::extract_tasks` — after each extracted task is added, per-task.
- `tasks.py::create_task` — after a manually-created task if it was given a category.
- `tasks.py::update_task` — after a category update.

### 3. Data model

New nullable FK on `Appointment`:

```python
source_task_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
)
```

Alembic migration required.

### 4. UI

No changes required — the existing Appointments page, calendar view, and `.ics`
export already work for any `Appointment` row regardless of how it was created.

## Testing

- `planner_agent`'s extraction tests get new cases for category parsing (valid value,
  invalid/missing value defaults to `None`, schema includes the enum).
- New `calendar_sync.py` tests: creates when category=appointment+due_date, no-op
  when category is anything else, no-op when due_date is null, no-op when a linked
  Appointment already exists (dedup), no-op when user_id is None.
- Integration-style tests at each of the three hook points confirming an `Appointment`
  row actually appears (or doesn't) end-to-end.
- Existing `Appointment`/`.ics`/task tests should be unaffected — regression-checked.

## Risks / open items for planning

- Exact JSON schema wording for the new `category` field and its default-on-invalid
  behavior is planning-time detail, following the same pattern as every other
  extraction module in this codebase.
- Whether `create_task`/`update_task` need the sync call inline or via an event is a
  planning-time call; given both are simple, already-transactional endpoints, an
  inline call (no new event type) is the default assumption unless planning finds a
  reason otherwise.
