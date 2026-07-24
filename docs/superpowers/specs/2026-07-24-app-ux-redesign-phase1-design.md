# App UX Redesign — Phase 1 (Foundation + Busiest-Page Polish)

## Status

Approved (brainstorming, with visual companion). First of an
open-ended series of redesign phases — "remake the whole app" is too
large for one spec, so this covers only the foundation: navigation
restructure, a consistent error/empty-state pattern, three concrete
bug fixes, and a visual polish pass on the three pages screenshots
showed most often. Everything else keeps its current design and is
explicitly deferred, not forgotten.

## Context

Prompted by a screen recording + 20 screenshots the user provided as
"inspiration for a friendlier app experience." Investigation before
designing anything (per brainstorming's explore-first step) found:

- **Two different systems are mixed in the screenshots**, not one
  app's history. Several show `collabrains.eu` — this app, live today
  (PDF viewer error, Document Detail, Tasks/"Acties", Login/Onboarding).
  Others show `admin.cbrains.de` / `portal.platform.cbrains.de`, a
  "NestJS API" status row, Mailcow, and a Grist-based webhook admin
  table — none of which exist in this stack (FastAPI/Python, no
  NestJS/Mailcow/Grist anywhere in the repo). This is CollaBrains v2,
  a separate, deliberately-superseded prior implementation
  (`support-cb/Cbrains-v2` on Codeberg) — confirmed by
  `models.py`'s own comment that `BugReport` was "migrated from
  CollaBrains v2's BugReport model/admin tab."
- **The apparent "223 open bug reports" screenshot is not current
  data.** Queried the live Postgres directly (read-only):
  `bug_reports` has 0 rows, `answer_feedback` has 0 rows, against 3
  real users / 19 real documents. The feature exists and works, it's
  simply never been used — not a data source to mine for
  prioritization. Confirmed with the user that screenshot is v2's own
  admin panel, reused for UX/feature *ideas* only, not literal scope.
- **Concrete, reproducible bugs exist in the current app today**,
  independent of any redesign: a raw `Unexpected server response (0)`
  browser-native error on PDF load failure, a raw `API 500: Internal
  Server Error` string shown to admins, a generic `Fout bij
  verifiëring. Probeer opnieuw.` on onboarding, and (traced to
  `apps/web/src/lib/taskUrgency.ts`) a literal `Invalid Date` label on
  appointment-type tasks with no due date, plus unbounded overdue-day
  counts (e.g. "2780 dagen verlopen") for genuinely old-but-valid
  deadlines.
- **An established design system exists and stays.** "Violet"
  (tokens, `CollaButton`/`CollaCard`/etc.) was deliberately chosen in
  an earlier phase over alternatives; user confirmed this redesign
  evolves it rather than replacing the visual identity.

## Decision

### 1. Main navigation — group, don't remove

Today's sidebar (`apps/web/src/lib/navigation.ts`) is 11 flat items +
Admin, no grouping. Restructure into 5 labeled sections, same items,
same routes, no behavior change:

- **Overview** — Dashboard
- **Records** — Documents, Entities, Cases, Vehicles
- **Planning** — Tasks, Calendar
- **AI Tools** — Chat, Legal Draft, Assistant
- **Account** — Settings, Admin (admin role only)

### 2. Admin — group, and place the 3 new stub areas

Today's Admin (`AdminDashboard.tsx`) is 6 flat tabs (Overview, AI
Usage, Health, Bugs, Users, Feedback). Regroup, and add 3 areas that
don't exist yet, inspired by v2's admin but not copying its tech:

- **Overview** (unchanged, ungrouped landing tab)
- **Users** — Users (existing)
- **Monitoring** — Health (existing), AI Usage (existing), **Product
  Analytics (new · stub)**
- **Feedback** — Bug Reports (existing, currently empty), Answer
  Feedback (existing), **Support Tickets (new · stub)**
- **Communication** — **Email Templates (new · stub)**

Every existing tab keeps its exact current route and behavior — this
is a relabel + regroup of what's there, plus net-new placeholders.

### 3. Settings — one new stub

**Notification Preferences (new · stub)**: Signal-per-document vs.
daily-digest choice, placed directly after the existing general
preferences card (language/date/time), before Passkeys. Nothing else
in Settings moves.

Noted but explicitly not decided in this phase: Settings is already a
long single-column stack of unrelated concerns (general prefs,
security, address history, org, billing, sharing). Splitting it into
sub-tabs is a reasonable future idea, flagged here, not designed or
built now.

### 4. Stub-area contract

Per explicit instruction: new areas (Support Tickets, Email Templates,
Product Analytics, Notification Preferences) ship as **dry
placeholders** — real nav entry, real page shell, real empty state,
Violet-styled — but with **no working backend, no persisted state,
and no functional buttons/links**. They exist so the information
architecture is complete; wiring them up is future work, out of scope
here.

### 5. Global error/empty-state pattern

Replace every raw browser/system-style error currently shown to users
(`Unexpected server response (0)...`, `API 500: Internal Server
Error`, and any other unwrapped exception text) with the same
Card + Badge convention already established in the Bugs admin tab:
a small status badge (e.g. "Couldn't load") + a plain-language
sentence + a retry action where one makes sense. This is app-wide, not
limited to the 3 polished pages below — every existing error/empty
state adopts this pattern as part of the foundation.

### 6. Three concrete bug fixes (real functional bugs, not just visual)

- **PDF viewer blob:// failure**: root-cause the fetch failure behind
  `Unexpected server response (0)`, fix it, and fall back to the new
  error pattern (with a working "Try again" / "Download instead") if
  it still fails for a legitimately unavailable file.
- **`taskUrgency.ts` date handling**: never render a raw `Invalid
  Date`. A task with no due date shows "No date on file". A valid but
  very old due date shows the actual date (e.g. "Overdue since 9 Apr
  2019") instead of an unbounded, alarming day-count.
- **Onboarding verification error**: root-cause what actually fails
  behind the generic `Fout bij verifiëring. Probeer opnieuw.` and
  either fix it or show a specific, actionable message instead of a
  catch-all retry prompt.

### 7. Visual polish — Documents list, Document Detail, Tasks list

The three pages the provided screenshots feature most. Existing
Violet DS components and tokens only — tighter grouping and spacing
on Document Detail's metadata sections, cleaner card treatment on
Tasks list (paired with the date-handling fix above), general
consistency pass on Documents list. No new information architecture,
no new components, no behavior change to existing functionality.

## Zero-regression requirement

Every route and feature that works today must still fully work after
this phase — this is a navigation/visual reorganization plus targeted
bug fixes, not a rebuild. Enforced by the existing test suites
(frontend vitest, backend pytest, Playwright e2e): all current tests
must keep passing, and the grouped-nav change needs a smoke check that
every existing route is still reachable through the new structure.

## Testing

- Existing automated suites (frontend/backend/e2e) must pass
  unchanged in behavior, updated only where DOM structure legitimately
  changes (nav grouping, relabeled admin tabs).
- New coverage: a nav-structure smoke test (every pre-existing route
  reachable via the new grouped sidebar/admin), regression tests for
  the three bug fixes (`taskUrgency.ts` edge cases: no due date, very
  old due date; onboarding error path; PDF load failure/retry).
- Stub pages get a minimal render/smoke test only (they render, nav
  reaches them, no console errors) — no logic exists yet to test.

## Out of scope (this phase)

- Wiring real backend logic behind any of the 4 stub areas.
- Splitting Settings into sub-tabs.
- Visual redesign of any page other than Documents list, Document
  Detail, and Tasks list — Entities, Cases, Vehicles, Chat, Legal
  Draft, Assistant, Calendar keep their current layout, gaining only
  the new nav shell and the benefit of the global error-pattern change.
- Any visual-identity change — Violet's tokens/components are the
  foundation throughout, not replaced.
- CollaBrains v2's actual technology (NestJS, Mailcow, Grist-based
  webhook admin) — used only as a feature/menu-structure idea source,
  never as something to integrate with or port code from.
