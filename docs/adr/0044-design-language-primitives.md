# 0044 — Design language: missing primitives + artifact archival

## Status

Accepted

## Context

The user supplied a design-language artifact ("CollaBrains — Violet Design
Language", extracted from Codeberg Cbrains-v2) and asked that (a) the app be
brought in line with it, (b) the artifact itself be preserved in the repo and
on the server, and (c) any cataloged component still missing be built.

An audit of `apps/web/src/styles/tokens.css` and `apps/web/tailwind.config.js`
against the artifact found the design tokens (colors, radii, shadows) and
most motion timing values already an exact match — this work predates the
artifact but was built from the same source design system. Of the ~24
cataloged components/patterns, ~17 already existed and matched
(`Card`, `Badge`, `Button`, `Modal`, `Drawer`, `DataTable`, `CommandPalette`/
`CommandCenter`, `BulkActionBar`, `FilterChips`, `InlineEditableText`,
`ShortcutsSheet`, `SplitView`, `Tooltip`, form primitives, `EmptyState`,
toast, loading bar). Seven were genuinely missing.

Full-page rebuilds implied by "redesign whole app" (Kanban board for Tasks,
document diff/redline view, a dedicated Deadlines & Reminders UI, an
Appointments/Calendar page) each require new backend data models and
endpoints comparable in scope to the preceding five-feature Fase-1 backend
marathon. Those are deliberately out of scope for this phase and flagged to
the user as a follow-up, rather than attempted here.

## Decision

1. Archive the artifact verbatim at `docs/design/violet-design-language.html`
   (repo root, not `apps/web`, since it's a design reference document, not
   part of the built app).
2. Build the seven missing primitives as small, focused, independently
   tested components under `apps/web/src/components/ui/`:
   `Breadcrumbs`, `Alert`, `Avatar`/`AvatarGroup`, `Stepper`, `Skeleton`,
   `Dropdown`, `Combobox`. Add the one supporting hook they share,
   `useClickOutside` (mirrors the existing `useEscapeToClose` pattern).
3. Add the artifact's `chipIn`/`cardIn`/`floaty`/`shimmer` keyframes to
   `tailwind.config.js` (the existing `ripple` keyframe was already there).
4. Wire `Breadcrumbs` + `Alert` into two existing pages
   (`DocumentDetail.tsx`, `CaseDetail.tsx`) as a working integration proof —
   replacing plain "← Back" links and raw `<p>` error text.
5. Defer the four backend-requiring full-page rebuilds; flag them explicitly
   for a follow-up conversation rather than scoping them in silently.

## Bugs found and fixed during test verification

Wiring `Breadcrumbs` into `DocumentDetail`/`CaseDetail` means the page title
now renders twice in the DOM (once in the breadcrumb trail, once in the
`<h1>`). Three existing tests broke because they queried by raw text
(`getByText`/`findByText`), which throws on multiple matches:

- `DocumentDetail.test.tsx` — `findByText("factuur-77621.pdf")` → changed to
  `findByRole("heading", { name: ... })`, which is also the more correct
  query for "asserts the page title is showing."
- `CaseDetail.test.tsx` — four occurrences of `findByText("Alpha matter")`
  (one real assertion, three used only to wait for load) → same fix.

Separately, `Combobox` intentionally renders already-selected options in its
(closed, CSS-hidden) listbox as disabled entries, so selected labels appear
twice in the DOM even before the dropdown opens. `Combobox.test.tsx`'s first
test asserted `getByText("Jane Doe")`, which is ambiguous for the same
reason. Fixed by asserting on the chip's remove button instead
(`getByRole("button", { name: "Remove Jane Doe" })`), which proves the chip
render without colliding with the listbox.

None of these were regressions in application behavior — the pages and
components work correctly. The tests were asserting via a query that stopped
being unique once a second, correct instance of the same text was added to
the page.

## Verification

- Full frontend suite run in the live `web` container:
  `docker compose exec -T web pnpm vitest run` → 45 files / 193 tests, all
  passing (7 new component test files + `useClickOutside.test.ts` + the two
  modified page test files, no regressions elsewhere).
- Production bundle rebuilt via `pnpm exec vite build` (bypasses the
  pre-existing, unrelated `tsc -b` failures documented in ADR 0039) and
  served; `https://v78281.1blu.de/` returns 200 with the CollaBrains SPA.

## Consequences

- The design system's token/motion layer needed no changes — confirms it was
  already built faithfully to this design language before the artifact was
  supplied.
- Seven new, small, independently-tested primitives are now available for
  any future page work (dropdown menus, multi-select comboboxes, avatars,
  stepper flows, skeleton loading states, alerts, breadcrumbs).
- Kanban board, document diff view, Deadlines/Reminders UI, and a Calendar
  page remain open — each needs backend design first and should be scoped
  as its own phase, not bundled into a frontend-only pass.
