# Phase 9 (slice 1): Navigation Shell + Dashboard Home

## Status
Approved (brainstorming)

## Context

The user's "Phase 9" brief asks for a full product overhaul: a new
landing page, onboarding, a modern dashboard, a restructured sidebar
covering ~15 nav destinations, and upgrades to every existing page,
plus mobile parity -- delivered as one PR per feature.

A repo survey found this is not a single buildable spec. `apps/web` is
a Vite + React SPA (not Next.js) with a mature custom UI kit and an
already-approved design system (`docs/design/violet-design-language.html`,
see [[2026-07-08-violet-design-language-design]]). The backend
(`services/api`, FastAPI) has real, fairly complete routers for
Documents, Cases, Tasks, Entities, Chat, Legal, Vehicles, and the
Manager Agent -- but **no** endpoints for Calendar, Contacts,
Notifications, Analytics, Timeline, or Workflow. The frontend has no
Landing page, no Onboarding, and no real Dashboard: `/` currently
renders the Documents workspace. Mobile (Expo/RN) covers roughly half
of web's routes.

Given this, Phase 9 is being decomposed into independently shippable
sub-projects, each with its own spec/plan/PR cycle. The user chose
**Navigation Shell + Dashboard Home** as the first slice: it is the
architectural foundation every later page slots into, it is the
highest-visibility win for existing/returning users, it is
auth-gated (no public-facing risk), and -- critically -- it needs no
new backend domains, so it can ship as a complete, non-placeholder
feature immediately.

Explicitly out of scope for this slice (would require either a new
backend domain or fabricated data, both disallowed by the "no
placeholder logic" constraint in the brief): Calendar/Agenda,
Contacts, a Notifications page/feed, Analytics, Timeline, Workflow,
"recent chats" (chat has no persistence layer today), drag-and-drop
or resizable widget layouts, any Entities -> "Knowledge" rebrand,
Landing page, Onboarding, and mobile nav changes. These become their
own future slices.

## Decision

**Routing.** `/` becomes the Dashboard (index route). The existing
Documents workspace moves to `/documents`. No other route paths
change. `ProtectedRoute`/post-login redirect logic continues to
target `/`, which now resolves to the Dashboard instead of Documents.

**Dashboard widgets.** Every widget is backed by an existing API --
nothing fabricated, no empty/placeholder cards:

- Welcome-back header (user display name, time-of-day greeting)
- AI Quick Actions -- shortcut cards to Chat, Legal Draft, Assistant,
  Tasks (link-only, reuse existing routes, no new logic)
- Recent Documents (`GET /documents`, last N by date)
- My Tasks (`GET /tasks`, open/upcoming)
- Pending Entity Reviews (existing review-queue count + link)
- Recent Cases (`GET /cases`)
- System Status -- admin-role only, from `GET /admin/health`

Each widget is an independent, collapsible card in a responsive grid
(CSS grid, standard Tailwind breakpoints, matching the existing
design-token layout patterns used elsewhere in `apps/web`). No
drag-and-drop reordering and no resize handles in this slice --
persisting an arbitrary per-user grid layout is real scope on its own
and the brief only asks for it "where appropriate." A future polish
slice can add it, backed by `PUT /preferences/me` which already
exists for storing per-user settings.

**Sidebar.** `apps/web/src/lib/navigation.ts` gets one new entry,
"Dashboard," first in the list, pointing at `/`. All existing labels
(Documents, AI Chat, Legal Draft, Tasks, Entities, Cases, Vehicles,
Assistant, Settings, Admin) are unchanged -- no relabeling ahead of
the page it describes actually changing. The current pending-entities
badge is upgraded into an alerts/bell dropdown in the sidebar header,
built on the same underlying pending-review data, structured so a
later Notifications slice can add more sources into the same
dropdown rather than replacing it. The existing `CommandCenter`
(Cmd+K palette) gets a visible trigger affordance in the sidebar/top
area instead of being discoverable only via keyboard shortcut.

## Testing

- Vitest unit tests for new Dashboard components/hooks (widget
  rendering, loading/empty states per widget, admin-only System
  Status gating).
- Routing tests updated for `/` (Dashboard) vs `/documents`
  (Documents workspace).
- Manual verification in the dev server: light and dark mode,
  responsive breakpoints, admin vs. non-admin view, sidebar bell
  dropdown, command palette trigger.
- Existing suite stays green -- no regressions to Documents, Chat,
  Legal, Tasks, Entities, Cases, Vehicles, Assistant, Settings, Admin.

## Follow-on slices (tracked, not built here)

Landing page + Onboarding; Calendar/Contacts/Notifications/Analytics/
Timeline/Workflow (new backend domains + pages); Chat/Documents/Tasks/
Knowledge page upgrades; Dashboard drag-and-drop/resize polish; Mobile
parity.
