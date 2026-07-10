# 0057 — Mobile pass round 3: table scroll, cramped control rows

## Status

Accepted

## Context

Follow-on to ADR 0050/0054 (mobile pass rounds 1-2). This round was
found by actually loading pages at a 375×667 viewport (iPhone SE width)
via Playwright and screenshotting, rather than reading code and
guessing — same discipline as every other "found via live testing" fix
in this project's history. Checked `Workspace`/`Documents`, `Tasks`,
`Cases`, `Vehicles`, and `CaseDetail` (with an attach control expanded)
live as an admin QA session; the first three had genuine mobile bugs,
`Cases` in its default state did not.

## Decision

- **`DataTable.tsx`**: the table's wrapper had `overflow-hidden` with no
  scrollable inner container, so on `Workspace` (Documents) — 4 columns
  including a `Status` badge — the rightmost column was silently
  clipped and completely unreachable on narrow viewports, not just
  visually cramped. Fixed by moving `overflow-hidden` to stay on the
  outer rounded/bordered wrapper (needed so the table's square corners
  don't poke out past the `rounded-2xl` border) and adding an inner
  `overflow-x-auto` div around just the `<table>`, plus
  `whitespace-nowrap` on header cells so column labels don't wrap
  mid-word before the scroll kicks in. This is a shared component used
  by every current and future `DataTable` consumer, so the fix applies
  automatically anywhere else it's used, not just `Workspace`.
- **`Tasks.tsx`**: the title + filter-buttons + view-toggle row was a
  plain `flex items-center justify-between` with no wrap behavior,
  unlike every other page fixed in rounds 1-2 — at 375px the title
  visually ran into the first filter button with no gap. Fixed with
  the same `flex-col gap-3 sm:flex-row sm:items-center sm:justify-between`
  pattern already established, plus `flex-wrap` on the inner controls
  group so the filter buttons and view toggle can wrap independently
  of the heading once they have their own row.
- **`Vehicles.tsx`**: `LicensePlateInput` renders a fixed `w-48`
  (192px) input styled like a physical plate, which doesn't shrink;
  next to it in a plain `flex items-center gap-3` row, the "Zoek op"
  button was squeezed into too little space and its own text wrapped
  onto two lines ("Zoek" / "op"). Fixed by adding `flex-wrap` to the
  row so the button drops to its own line — where it has the full
  card width available — instead of fighting for space beside a
  non-shrinking sibling.
- **`CaseDetail.tsx`**: the expanded `AttachControl` state (a `<select>`
  plus "Attach" plus "Cancel", all in one `flex items-center gap-2`
  row) overflowed its Card on mobile badly enough that **"Cancel" was
  completely invisible and unreachable**, not just visually tight —
  this was the most severe bug found this round, since there was no
  way to back out of the attach flow without it. Fixed the same way as
  `Vehicles.tsx`: `flex-wrap` on the row.

## Verification

- Full frontend suite (live `web` container, freshly rsynced): 48
  files / 217 tests passed, unchanged — none of these fixes touched
  text content or DOM structure in a way any existing test asserts on.
- `pnpm exec vite build` succeeded, fresh content-hashed bundle
  confirmed loaded (checked `script[src]` hash after navigating, per
  the stale-bundle lesson from ADR 0054/0055).
- Real browser verification via Playwright at a 375×667 viewport for
  all four fixes, before and after: `Workspace`'s Status column
  confirmed reachable via horizontal scroll (`scrollWidth 399 >
  clientWidth 341` on the table wrapper, and visually scrolled to see
  the `ready` badges); `Tasks`' header now stacks title above controls
  instead of running together; `Vehicles`' search button now renders
  on one line on its own row; `CaseDetail`'s Attach/Cancel buttons are
  both now visible and tappable when a section's attach control is
  expanded. Throwaway QA admin user created and deleted after, same as
  every other round.

## Consequences

- The `DataTable` fix is a shared-component change, so it retroactively
  fixes any other page that renders a table with enough columns to
  overflow narrow viewports, without needing a separate per-page fix.
- `flex-wrap` on a controls row (as opposed to the `flex-col ...
  sm:flex-row` pattern used for page-level header rows) is now used
  twice this round for *rows nested inside a Card* rather than
  top-level page headers — worth treating as the standard fix shape
  for "a handful of same-priority inline controls that don't need a
  breakpoint-gated stacked/inline distinction, just permission to wrap
  when they don't fit."
- Remaining mobile-pass scope is unchanged from ADR 0054's estimate:
  most of ~50 route files have not been individually checked at a
  narrow viewport. This round targeted the pages most likely to have
  genuine bugs (dense control rows, tables) rather than working
  through the full file list — same "spot the highest-risk shapes"
  approach as rounds 1-2, not a claim of full coverage.
