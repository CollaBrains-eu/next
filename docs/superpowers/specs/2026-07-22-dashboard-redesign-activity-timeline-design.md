# Dashboard redesign + Activity Timeline — Design

## Status

Approved (brainstormed 2026-07-22)

## Context

Sub-project 2 of the app-shell premium redesign (design system → **layout,
shipped** → dashboard → documents → AI chat → login; see
`docs/superpowers/specs/2026-07-22-design-system-sidebar-layout-design.md`
for sub-project 1, already live). The original brief asked for an
"intelligent overview" replacing simple tiles, covering: recent documents,
open actions, AI insights, an activity timeline, and statistics.

Audited `apps/web/src/routes/Dashboard.tsx` (315 lines) before assuming a
rebuild was needed: it already has a hero greeting banner, 4 stat tiles
(documents/actions/overdue/cases), a quick-actions grid, and a
`DashboardWidgetCard`-based grid (recent documents, my tasks, pending
entity reviews, recent cases, admin-only system status). Most of the brief
is already met structurally — this is a visual pass plus one genuinely new
widget, not a rebuild.

Two brief items don't exist yet: "AI inzichten" and "activiteit timeline".
Checked the backend (`services/api/src/api/`) before designing either:
there's an in-process event bus (`events.py`, Phase 8a/ADR 0017) durably
logging document/task/workflow lifecycle events to Redis Streams, but it's
**write-only** (`publish()`/`subscribe()`, no read/query function) and its
event vocabulary (`EmbeddingsCreated`, `OCRCompleted`, `DocumentClassified`,
...) is internal/technical, not what a user wants to see in a timeline.
Decided against reading it for that reason — see Backend section below for
what the Activity Timeline uses instead.

Split from AI Insights during brainstorming: AI Insights needs a real LLM
call (`api.ai_gateway.chat_completion`), and this host's own documented
capacity numbers (`docs/runbooks/capacity.md`) show chat requests taking
anywhere from ~2s to 55s+ depending on concurrency, CPU-only, no GPU. That
needs a deliberate caching/refresh-cadence design, not a "call it on page
load" implementation — genuinely different shape of work from a DB
aggregation query. Deferred to its own follow-up spec.

## Goals

1. Visually restyle the existing dashboard (hero banner, stat tiles, quick
   actions, widget cards) using the design-system tokens shipped in
   sub-project 1 (`--gradient-brand`, `.glass-surface`, `ds-*` radii) —
   without restructuring what already works.
2. Add a new Activity Timeline widget: a unified, recency-sorted feed of
   the user's recent documents/tasks/cases/entities, each correctly scoped
   by that resource's own real visibility rule (not a new, parallel
   authorization scheme).
3. Keep every existing widget's data-fetching, loading, and empty-state
   behavior working exactly as it does today — this is additive plus a
   restyle, not a rewrite of `Dashboard.tsx`'s data layer.

## Non-goals

- AI Insights — separate follow-up spec (see Context).
- Redesigning `DashboardWidgetCard` itself (the shared widget shell) — it
  already handles loading/skeleton, empty state, and collapse/expand
  correctly; the Activity Timeline widget uses it as-is.
- Reading from the Redis event bus (`events.py`) — decided against, see
  Context.
- Documents page, AI Chat, Login redesigns — separate specs, later in the
  sequence.
- Changing what counts as "recent" for the existing per-widget lists
  (recent documents/tasks/cases already each show their own top-5) — the
  Activity Timeline is a new, separate, cross-resource feed, not a
  replacement for those.

## Backend: `GET /dashboard/activity`

New `services/api/src/api/dashboard_router.py` + a service function in a
new `services/api/src/api/dashboard.py`, registered in `main.py` alongside
the other routers (no path prefix is set at `include_router` time in this
codebase — every router declares its own full path, e.g. `cases_router.py`
uses `@router.get("/cases")` directly — so this new route is declared as
`@router.get("/dashboard/activity")`).

**Scoping, per resource, matching each resource's existing real visibility
rule** (not a new parallel scheme):
- Documents: `Document.owner_id == current_user.id` (same rule
  `documents.py`'s list endpoint already uses).
- Cases: `Case.user_id == current_user.id` **or** an `accepted`
  `CaseMember` row for that case+user — matching how `list_cases` already
  includes shared cases (Phase 26 workspace sharing), not just owned ones.
- Entities: `Entity.owner_id == current_user.id` (same rule `entities.py`
  already uses; `pending_review` entities are included — a newly-extracted
  entity awaiting review is legitimately "recent activity").
- Tasks: `Task.created_by == current_user.id`, **or** (since `created_by`
  is nullable — tasks auto-extracted by the Planner Agent have no creator)
  `Task.document_id` pointing at a document the user owns. Matches how the
  existing Tasks page already surfaces auto-extracted tasks to the
  document's owner.

**Implementation pattern**: async SQLAlchemy `select()` per model (same
shape as `cases.py`'s existing `get_case_dashboard` — no new query-building
abstraction), each result mapped to a common shape, then merged and sorted
by `created_at` descending, capped at 15 items:

```python
class ActivityItemOut(BaseModel):
    type: Literal["document", "task", "case", "entity"]
    id: UUID
    title: str
    created_at: datetime
    link: str  # frontend route, e.g. f"/documents/{id}"
```

`title` is `Document.title` / `Task.title` / `Case.name` / `Entity.name`
respectively. `link` is built server-side (`/documents/{id}`,
`/documents/{id}` for a task with a `document_id` else `/tasks`,
`/cases/{id}`, `/entities/{id}`) so the frontend doesn't need per-type
routing logic beyond rendering an `<a>`.

## Frontend

**`ActivityTimeline` widget** (`apps/web/src/components/ActivityTimeline.tsx`,
new): fetches `GET /dashboard/activity` (new `listDashboardActivity()` in
`api.ts`), renders inside the existing `DashboardWidgetCard` shell
(loading/empty states come for free — no shell changes). Each item shows a
per-type icon (reuse the `lucide-react` icons already mapped in
`navigation.ts` — `FileText` for document, `CheckSquare` for task,
`FolderOpen` for case, `Users` for entity, so the same icon language
already established in the sidebar carries through), the title as a link,
and a relative timestamp (reuse the existing `useDateFormat` hook already
used elsewhere on this page). Placed in the existing widget grid in
`Dashboard.tsx` alongside the current five widgets.

**Visual restyle** (existing elements, no structural change):
- Hero banner: currently `bg-gradient-to-br from-accent to-accent-hover`
  (a two-stop accent gradient already) — swap to `bg-gradient-brand`
  (the sub-project-1 token) so the hero and the sidebar's active-item/brand
  accents visually match instead of using two different violet gradients.
- Stat tiles and widget cards: adopt `rounded-ds-lg` (sub-project 1's named
  radius scale) in place of the current ad hoc `rounded-2xl`, for
  consistency with the new sidebar chrome — same visual size, named token
  instead of a guessed Tailwind utility.
- No new colors, no glass-surface usage identified as fitting here on
  inspection — glass-surface suits floating/overlay panels (already used
  nowhere on this solid-background page); forcing it in would contradict
  the brief's own "niet overdreven" direction. Noted as available if a
  concrete fit turns up during implementation, not prescribed blindly.

## Testing

**Backend** (`services/api/tests/test_dashboard_router.py`, new): the
scoping rules above are the real correctness risk, so they're what gets
tested directly, using this project's established disposable-test-user
pattern (create throwaway LDAP+Postgres users, tear down after):
- A document owned by user A does not appear in user B's activity feed.
- A case shared with user B via an *accepted* `CaseMember` invitation
  appears in B's feed; a *pending* (not yet accepted) invitation does not.
- A task with `created_by IS NULL`, extracted from a document owned by
  user A, appears in A's activity feed (via the document-ownership
  fallback) and not in user B's.
- Items from all four resource types merge into one feed sorted by
  `created_at` descending, capped at 15.

**Frontend** (`ActivityTimeline.test.tsx`, new; `Dashboard.test.tsx`,
extended): widget renders items with correct icon/title/link per type;
loading and empty states (reusing `DashboardWidgetCard`'s existing,
already-tested behavior — just confirming this widget wires into it
correctly, not re-testing the shell itself).

## Open questions resolved during brainstorming

- **AI Insights**: confirmed deferred to its own follow-up spec, given its
  distinct LLM-latency/caching design needs.
- **Activity Timeline data source**: confirmed a new backend DB-aggregation
  endpoint (not client-side synthesis, not the Redis event bus).
