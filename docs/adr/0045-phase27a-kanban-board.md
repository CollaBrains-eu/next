# 0045 — Phase 27a: Kanban board (Tasks)

## Status

Accepted

## Context

Scoped in `docs/roadmap/phase-27.md`. The Tasks page had only a flat
open/done list; the design-language artifact
(`docs/design/violet-design-language.html`) calls for a drag-and-drop
board with `todo` / `progress` / `done` columns.

## Decision

- Added `Task.position: int` (default `0`) via migration `d1a4e7f9c2b6`,
  backfilling existing rows with a per-status sequence ordered by
  `created_at`.
- Extended the status whitelist in `PATCH /tasks/{id}` from
  `("open", "done")` to `("open", "in_progress", "done")`.
- `TaskUpdate` gained an optional `position: int | None`. `update_task`
  now always re-sequences the target status column into a clean,
  contiguous `0..N-1` ordering that includes the moved task — whether the
  move changes status, position, or both — rather than trying to patch a
  single row's position in place. This avoids the column drifting into a
  sparse/inconsistent state after repeated moves, and keeps the frontend's
  "index in the column" concept always valid to send back as `position`.
- `Tasks.tsx` gained a List/Board view toggle. List view is unchanged
  (same filter tabs, same fetch-by-status). Board view always fetches all
  tasks (no status filter) and renders the new `KanbanBoard` component,
  grouping client-side into the three columns and sorting by `position`.
- `KanbanBoard` uses native HTML5 drag-and-drop (`draggable`,
  `dataTransfer.setData`/`getData`), matching the artifact's plain-DOM
  pattern rather than adding a drag-and-drop library. Dropping on a
  specific card inserts before it; dropping on empty column space appends
  to the end.
- Did not scope the Kanban list query to a document or case — the board
  is global across all tasks, same as the existing List view.

## Deviation from the phase-27 scope doc

The scope doc proposed changing `list_tasks`'s default ordering to
`(status, position)`. Implementing this surfaced a real regression: the
existing List view relies on `created_at.desc()` (newest first), and
switching the shared endpoint's default order would have flipped that to
oldest-first per status group (since `position` is backfilled in
ascending `created_at` order). Fixed by leaving `list_tasks`'s ordering
untouched and having `KanbanBoard` sort by `(status, position)`
client-side after fetching — the Board view already fetches the full,
unfiltered list, so no extra request is needed either way.

## Test-writing note (shared, non-isolated dev DB)

Two of the new backend tests initially asserted absolute position values
(e.g. "the first task appended to `in_progress` lands at position 0").
These failed on a full suite run because `services/api` has no
per-test DB isolation (documented since ADR 0004-era test conventions) —
prior test runs leave real rows in `tasks` with real statuses, so a fresh
`in_progress` column is never actually empty. Fixed by asserting
relative invariants instead (each append lands one position after the
previous; N specific tasks end up at N distinct positions) rather than
assuming a pristine table. Kept `test_extracted_task_defaults_to_position_zero`
as an absolute assertion since that's a static model default unaffected by
other rows.

## Verification

- Migration `d1a4e7f9c2b6` applied to the live DB via the usual isolated
  throwaway-container pattern; `alembic current` confirmed `d1a4e7f9c2b6
  (head)`.
- Full backend suite (`uv run pytest tests/ -q`) in the same isolated
  container: 326 passed, 14 failed — the exact pre-existing baseline
  (`test_ai_gateway`, `test_chat` x2, `test_documents` x3, `test_entities`
  x7), zero new failures.
- Full frontend suite (`pnpm vitest run` in the live `web` container): 46
  files / 200 tests passed, including the new `KanbanBoard.test.tsx` (5
  tests) and the extended `Tasks.test.tsx`.
- Production bundle rebuilt (`pnpm exec vite build`); `https://v78281.1blu.de/`
  returns 200, `/tasks` (API, unauthenticated) returns 401 as expected.

## Consequences

- `in_progress` is now a real, first-class task status other code
  (notifications, planner agent, future automation) can start using.
- Board view intentionally shows every task regardless of case/document —
  a per-case board was explicitly out of scope (see phase-27 doc); revisit
  if that turns out to matter in practice.
- Phase 27b (Calendar/Appointments) remains open, scoped but not built.
