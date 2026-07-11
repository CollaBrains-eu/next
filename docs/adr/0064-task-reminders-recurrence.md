# 0064 — Deadlines & Reminders: recurrence + due-date notifications

## Status

Accepted

## Context

ADR 0063's audit of the Violet Design Language artifact flagged
"Deadlines & Reminders" as one of the artifact-only sections that would
need real backend work to become an actual product feature — the same
category Kanban was in before ADR 0045 gave it one. Asked which P3 item
to scope next, the user picked this one.

`Task` (ADR 0004) already carries `due_date`, and its own docstring says
almost exactly this: "no calendar sync, no recurrence... until there's a
real scheduling/notification feature to justify more structure." That
feature is this one — the smallest gap of the three P3 candidates
(Reminders / Calendar / document diff) since it extends an existing
entity rather than needing a new one.

Two real gaps found while scoping, not assumed:

1. **There is no way to create a task manually today.** `tasks.py` only
   has `POST /documents/{id}/extract-tasks` (Planner Agent), `GET
   /tasks`, and `PATCH /tasks/{id}` (status/position only, for the
   Kanban board). The artifact's "Add reminder" form has never had
   anything to submit to.
2. **`Task.assignee` is free text, not a user FK** (`created_by` is the
   only real link to `users`). A notification system can't resolve
   "assignee" to a phone number the way `documents.py`'s
   `_notify_owner` resolves `document.owner_id` — it has to notify
   `created_by` instead, mirroring that exact pattern.

No task-queue infrastructure exists in this stack by deliberate choice
(ADR 0002 skipped Elasticsearch, ADR 0004 skipped Celery, ADR 0007's
proactive-notification skeleton is event-triggered from within a
request, not time-triggered) — the established pattern for anything
that needs to fire on a schedule rather than in response to a request is
a plain script on host cron, same as `infra/monitoring/watchdog.sh` and
`infra/backup/backup.sh`. Due-date reminders are the first genuinely
time-triggered case, so that's what this uses.

## Decision

**Schema** (new migration, chained onto the current head
`3b63cde925a6`):
- `tasks.recurrence_rule: str | None` — one of `null` (one-time),
  `"daily"`, `"weekly"`, `"monthly"`, matching the artifact's
  cadence-chip options exactly (no cron-expression generality; nothing
  in this product needs more than that, and a free-form cron field
  would need its own validation/parsing story for no current benefit).
- `tasks.notified_at: datetime | None` — set when a due/overdue
  notification has been sent for the task's *current* due date, so the
  cron script doesn't re-notify every run. Cleared when the due date
  changes (edit) or a recurring task rolls to its next occurrence.

**API** (`services/api/src/api/tasks.py`):
- New `POST /tasks` — manual creation (`title`, `description?`,
  `due_date?`, `assignee?`, `recurrence_rule?`), `source="manual"`,
  `created_by=current_user.id`. This is the endpoint the artifact's
  "Add reminder" form actually needed.
- `TaskUpdate` gains optional `due_date`, `recurrence_rule` (in addition
  to the existing `status`/`position`) so an existing task can be
  edited. `status`/`position` stay required-shaped as today —
  `moveTask`/`updateTaskStatus` on the frontend don't change.
- When a recurring task (`recurrence_rule` set) is marked `done`, the
  endpoint creates the next occurrence (new row, `due_date` advanced by
  the cadence, `notified_at` cleared, same title/description/assignee/
  recurrence_rule) rather than mutating the completed one — keeps
  completed-task history intact instead of silently resetting a row
  in place.

**Notifications** (`services/api/scripts/notify_due_tasks.py`, run via
host cron, same shape as `watchdog.sh`):
- Queries open/in_progress tasks where `due_date <= today` and
  `notified_at` is null, joins `created_by` → `users.phone_number`.
- Reuses `signal_client.send_signal_message` unmodified (already
  best-effort: silently no-ops if Signal isn't configured or the user
  has no linked phone, exactly like `_notify_owner`).
- Sets `notified_at = now()` after a successful send so the next cron
  run doesn't repeat it.

**Frontend**:
- New task-creation control in `Tasks.tsx`, reusing the artifact's
  cadence-chip pattern (`once`/`daily`/`weekly`/`monthly`) translated
  into a small set of `Button`-style toggles — not a new component,
  the existing `Button` primitive already covers this shape.
- Due-date text upgraded to a due-badge (overdue / due today / upcoming)
  matching the artifact's `.due-badge` variants, computed client-side
  from `due_date` vs. today — no new backend field needed for this part,
  it's a presentation-only concern.

## Verification plan

No Docker/Postgres/uv available in this sandboxed environment, so a
scratch local Postgres 16 + pgvector was built by hand (`initdb` on a
throwaway data dir + port 5433, `pip install -e .` into a venv instead
of `uv`) specifically to run the real `pytest` suite against a real
database rather than shipping unverified backend code — the same bar
ADR 0044 held itself to via Docker, adapted to what's actually available
here. Migrated cleanly to the true current head (`3b63cde925a6`,
confirmed via `alembic current`) before any new code was written.
Frontend changes verified via `pnpm vitest run` (already proven to work
locally this session, see PR #57).

## Consequences

- `Task` remains the single actionable-item entity — no new
  "Reminder" table, matching how the artifact's "Deadlines & Reminders"
  section is really just Tasks with due dates, not a separate concept.
- The cron-script notification pattern is now proven for two different
  triggers (document-ready, task-due) — a template for the next
  time-triggered feature instead of reaching for Celery.
- Calendar/Appointments and document diff/redline remain deferred,
  unchanged from ADR 0063.
