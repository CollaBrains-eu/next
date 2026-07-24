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
  independent of any redesign — but each was individually verified
  against actual current-app code, not assumed from a screenshot,
  after the onboarding screenshot turned out to be a false lead (see
  below): a raw `Unexpected server response (0)` browser-native error
  on PDF preview, traced to `previewDocumentFile()`
  (`apps/web/src/lib/api.ts:810-815`) opening a `blob:` URL via
  `window.open()` in a new tab — a well-documented WebKit/iOS Safari
  limitation where blob URLs don't reliably survive the handoff to a
  new browsing context; and (traced to
  `apps/web/src/lib/taskUrgency.ts`) a literal `Invalid Date` label on
  appointment-type tasks with no due date, plus unbounded overdue-day
  counts (e.g. "2780 dagen verlopen") for genuinely old-but-valid
  deadlines.
- **The onboarding "Fout bij verifiëring. Probeer opnieuw." screenshot
  is also a false lead, like the 223-bug-reports one.** Current
  `Onboard.tsx` is a token-link flow (`?token=...` →
  valid/invalid/loading) with no phone-number field, no verification
  retry button, and no matching translation string in any of
  `apps/web/src/locales/{en,nl,de}.json`. The screenshot is v2's
  phone-based onboarding — dropped from the bug-fix list entirely
  rather than sending an implementer after a bug that doesn't exist
  here. The raw `API 500: Internal Server Error` string (admin Email
  Templates test-send) is real but not independently root-caused —
  it's covered by the general error-pattern rollout (section 6) rather
  than as its own numbered bug fix.
- **An established design system exists and stays.** "Violet"
  (tokens, `CollaButton`/`CollaCard`/etc.) was deliberately chosen in
  an earlier phase over alternatives; user confirmed this redesign
  evolves it rather than replacing the visual identity. The user
  separately shared their own Violet DS reference artifact (colors,
  motion tokens, full component catalog) — this is the definitive
  visual source for every mockup and every implementation task below,
  not an approximation of it.
- **Full router audit, not just screenshot-derived ideas** (per
  explicit instruction to "check every option," not only what the
  screenshots showed): every backend router in `main.py` was checked
  against the frontend's actual routes. Two real backends have **zero
  frontend surface** — not stubs, fully working: `api/facts.py`
  (list/approve/reject `UserFact` rows) and `api/memories.py`
  (list/delete AI `Memory` rows). Nothing in `apps/web/src` references
  either. This is exactly the "AI knowledge about you" gap the user
  named directly. `api/tools_router.py` (`GET /tools`, listing
  available AI tools) is also frontend-less — lower priority, a
  transparency nice-to-have rather than something to manage.
  `decisions_router` (AI decision rationale) already has a real
  consumer (`CaseDetailContent.tsx`) — not a gap. `preferences_router`
  is exactly what Settings' general-prefs card already calls — not a
  gap either.

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

### 4. Settings — AI & Knowledge (new, real, not a stub)

Unlike the stub areas above, this wires up backends that already
exist and work — it's real functionality, not a placeholder:

- **Facts** — list the user's reviewed/pending `UserFact` rows
  (address, employer, etc. extracted by the AI), approve or reject
  pending ones. Backend (`api/facts.py`) is complete; only the page
  is missing.
- **Memories** — list what the AI has stored about the user, delete
  any entry. Backend (`api/memories.py`) is complete; only the page
  is missing.
- **AI Tools** (lower priority, same section) — read-only list of
  tools the AI assistant can currently use, for transparency. Backend
  (`api/tools_router.py`) is complete; only the page is missing.

Placed in Settings, grouped under a new "AI & Knowledge" heading,
after Notification Preferences and before Passkeys — the user
explicitly asked for this under profile settings.

### 5. Stub-area contract

Per explicit instruction: new areas (Support Tickets, Email Templates,
Product Analytics, Notification Preferences) ship as **dry
placeholders** — real nav entry, real page shell, real empty state,
Violet-styled — but with **no working backend, no persisted state,
and no functional buttons/links**. They exist so the information
architecture is complete; wiring them up is future work, out of scope
here. Facts/Memories/AI Tools (section 4, above) are explicitly **not**
under this contract — they get fully working pages against their
already-complete backends.

### 6. Consistent error pattern for everything new in this phase

Correction after implementation research: an `Alert` component
(`apps/web/src/components/ui/Alert.tsx`, variant `info/success/warning/
danger`, already used in `DocumentDetailContent.tsx`) already exists
and is the right reuse target — not a new Card+Badge pattern invented
for this phase. Every new/changed surface in this phase (Facts,
Memories, AI Tools, the 3 stub tabs, the Notification Preferences
stub) uses `Alert` for its error states.

Narrowed from "app-wide" to "everything this phase touches": a grep
across the current app found 18 existing files rendering errors as a
plain `<p className="text-danger">{error}</p>` rather than via
`Alert`. Retrofitting all 18 is a separate, higher-regression-risk
sweep with its own testing burden, disconnected from any bug this
phase actually found — the two concrete raw-error screenshots (the
PDF viewer, and an "API 500" on an Email Templates feature that
doesn't exist in this app yet, see below) are handled directly by
their own items (section 7, and the new Email Templates stub
respectively), not by a blanket retrofit. Flagged as a reasonable
future cleanup, not done here.

### 7. Two concrete bug fixes (real functional bugs, not just visual)

- **PDF viewer blob:// failure**: `previewDocumentFile()`
  (`apps/web/src/lib/api.ts:810-815`) calls
  `window.open(URL.createObjectURL(blob), "_blank")`. Fix: navigate the
  *same* tab to the blob URL instead of opening a new one (or render
  inline via an `<iframe>`/`<embed>` in the document detail view) so
  the blob URL never has to cross a browsing-context boundary. Fall
  back to the new error pattern (section 6) with a working "Try again"
  / "Download instead" for genuinely unavailable files.
- **`taskUrgency.ts` date handling**: never render a raw `Invalid
  Date`. A task with no due date shows "No date on file". A valid but
  very old due date shows the actual date (e.g. "Overdue since 9 Apr
  2019") instead of an unbounded, alarming day-count.

(A third item, an onboarding verification error, was in the original
screenshot set but confirmed not reproducible in this codebase — see
Context above. Dropped rather than fabricated.)

### 8. Visual polish — Documents list, Document Detail, Tasks list

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
  the two bug fixes (`taskUrgency.ts` edge cases: no due date, very
  old due date; PDF preview same-tab navigation / failure-and-retry).
- Stub pages get a minimal render/smoke test only (they render, nav
  reaches them, no console errors) — no logic exists yet to test.
- Facts/Memories/AI Tools pages get real coverage against their
  existing backends: list rendering, Facts approve/reject, Memories
  delete, matching the rigor of any other functional page — they are
  not stubs.

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
