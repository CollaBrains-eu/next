# 0050 — Mobile: per-page overflow fixes (first pass)

## Status

Accepted

## Context

Follow-on to the mobile shell (ADR 0049). With the Sidebar/Layout drawer
working, the question was which of the ~46 remaining files actually
need responsive work versus which already degrade gracefully at phone
width because they were already built on flex/grid layouts. Rather than
touching all 46 files blindly, surveyed a handful of high-traffic pages
in a real 390×844 browser session (Documents, Cases, Entities, Tasks
Kanban, Chat, Admin, DocumentDetail) using a throwaway admin QA session
(Postgres row + self-signed JWT, same pattern as ADR 0049, cleaned up
after) and fixed only what was actually broken.

## What was already fine (no changes)

- Documents list, Cases (empty state), AI Chat, the Tasks Kanban board
  (`sm:grid-cols-3` from Phase 27a already collapses to one column
  correctly below `sm:`), and the Admin AI-usage table (narrow enough
  columns that the table doesn't overflow, even without a dedicated
  `overflow-x-auto` wrapper).

## What was broken, and the fix

- **`Entities.tsx`**: the filter row (search input + 2 selects + "Review
  pending →" link) was a single `flex items-center justify-between`
  with no wrap — the link got squeezed into overlapping the selects.
  Changed the outer container to `flex-col gap-3 sm:flex-row
  sm:items-center sm:justify-between` (stacks below `sm:`, row above)
  and the form to `flex-wrap` with the search input `w-full sm:w-auto`.
  Separately, entity names had no truncation — a long one (`3RO.1057.
  402.890495...`) overflowed the list row and pushed the type badge off
  the visible area. Added `min-w-0 truncate` on the name span (the
  `min-w-0` is required for `truncate` to work inside a flex child —
  without it the row just grows instead of clipping) plus a `title`
  attribute so the full name is still available on hover/long-press.
- **`AdminDashboard.tsx`**: the tab bar (`Overview | AI usage | Health |
  Bug reports | Users`) had no overflow handling — "Users" (the newest
  tab, ADR 0048) was clipped off the right edge with no way to reach
  it. Added `overflow-x-auto` to the tab row and `shrink-0` to each tab
  button, making it horizontally swipeable. Verified by scrolling the
  container programmatically and confirming "Users" becomes reachable.
- **`DocumentDetail.tsx`**: the header row (title + status line on the
  left, Summarize/Delete buttons on the right) was a non-wrapping `flex
  items-start justify-between` — the Delete button was clipped off the
  right edge entirely, not just visually cramped. Changed to `flex-col
  gap-3 sm:flex-row sm:items-start sm:justify-between` (stacks below
  `sm:`), added `min-w-0 truncate` to the title and `flex-wrap` to the
  metadata line, `shrink-0` on the button group.
- **`CaseDetail.tsx`**: same title-overflow risk as Entities/
  DocumentDetail (case name + a status-toggle badge button) — added the
  same `min-w-0 truncate` / `shrink-0` pairing preemptively, since it's
  the identical pattern already proven broken twice elsewhere on this
  page. Not independently confirmed broken in the survey (no case with
  a long enough name existed in the live data to trigger it), but the
  fix is low-risk and consistent with the other two.

## Verification

- Full frontend suite (live `web` container): 47 files / 211 tests
  passed — no test asserted on any of the changed classNames, so no
  test updates were needed.
- Real browser re-verification (same throwaway QA session, 390×844)
  after rebuilding `dist/`: Entities' filter row now wraps cleanly with
  "Review pending →" on its own line and the long entity name now
  ellipses correctly; the Admin tab bar's "Users" tab is reachable by
  scrolling (confirmed via `scrollLeft` — bounded at 77px, i.e. a real,
  finite overflow, not an unbounded/broken one); DocumentDetail's
  Delete button is now fully visible instead of clipped.

## Consequences

- Three of the ~46 remaining files are done; roughly 43 are unaudited.
  The pattern found here (unwrapped `flex ... justify-between` header/
  toolbar rows, and un-truncated user-generated-content text in list
  rows) is the most likely recurring issue elsewhere — worth checking
  for that specific shape first in any follow-up pass rather than
  re-surveying from scratch.
