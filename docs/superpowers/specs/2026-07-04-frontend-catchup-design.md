# Phase 17 — Frontend Catch-Up: Sidebar Shell + Case Workspace, Assistant, Settings

## Status
Draft, pending final user sign-off before implementation.

## Context

Every backend phase since Phase 8c (Planning Engine, Tool
Registry/MCP/Permissions/Discovery, Knowledge Graph 2, Multi-Agent
Manager, Autonomous Workflows, Personal AI, Enterprise, Learning
Platform, Case Workspace — 8 phases in total) shipped API-only, with no
corresponding UI in `apps/web`. The frontend still only has Phase 5's
pages: Documents, AI Chat, Legal Draft, Tasks, Entities. Everything
built since is only reachable via direct API calls.

This phase closes the highest-value slice of that gap: UI for Case
Workspace (Phase 16), the Manager Agent (Phase 11), and Personal AI
preferences (Phase 13) — chosen over the other five backend-only areas
(Planning Engine, Tool Registry/MCP, Knowledge Graph Decisions,
Autonomous Workflows' internals, Organizations/admin policies) as the
most user-facing and highest-leverage right now.

Alongside the three new pages, this phase also redesigns the app shell
from the current top nav to a persistent left sidebar (explicitly
requested during brainstorming, aiming for a more polished,
enterprise-SaaS feel) — a bigger, coupled change that the three new
pages get built into rather than around.

## Goal

A left-sidebar app shell, plus three new pages (Cases, Assistant,
Settings) reachable from it, giving real UI to three backend
capabilities that currently only exist as raw endpoints.

## Scope

**In scope**:
- Sidebar/Layout shell redesign replacing the current top nav.
- Two shared UI primitives (`Card`, `EmptyState`) used only by the
  three new pages.
- Case Workspace UI: list, create, detail dashboard with attach flows
  for documents, tasks, and decisions.
- One small backend addition: `GET /decisions` (list the caller's own
  decisions), needed to populate the Decisions attach-picker — the only
  one of the three attach targets with no existing list endpoint.
- Manager Agent UI: a new `/assistant` page.
- Personal AI preferences UI: a new `/settings` page with a language
  select.

**Explicitly out of scope, not attempted here**:
- Retrofitting the existing 5 pages (Documents, Chat, Legal, Tasks,
  Entities) onto the new `Card`/`EmptyState` primitives — they keep
  their current inline styling. Only the 3 new pages use the new
  primitives.
- UI for Planning Engine (`/plans`), Tool Registry/MCP, Knowledge Graph
  Decisions (beyond what Case Workspace's attach-picker needs),
  Organizations/admin policies, and Learning dataset export — all
  still backend-only after this phase, left as candidate future work.
- Any new frontend automated test pattern beyond what already exists
  (see Testing, below) — this phase follows the existing convention,
  not a new one.

## Phased Delivery

Following this project's established convention for every other
multi-capability phase (1a/1b, 5a/5b/5c, 9a-9d, etc.): a stacked
sequence of sub-phases, each its own branch and PR, rather than one
single Phase 17 PR.

- **17a — Shell redesign**: `Sidebar`/`Layout` extraction, the two new
  shared primitives, `App.tsx` reduced to a route table. Ships and
  merges alone first — every later sub-phase builds its page inside
  this new shell.
- **17b — Case Workspace UI**: `Cases.tsx`, `CaseDetail.tsx`, the
  `api.ts` additions, and the `GET /decisions` backend addition.
  Branches from `main` after 17a merges.
- **17c — Manager Agent / Assistant UI**: `Assistant.tsx` + its
  `api.ts` additions. Branches from `main` after 17a merges (no
  dependency on 17b).
- **17d — Personal AI Preferences / Settings UI**: `Settings.tsx` + its
  `api.ts` additions. Branches from `main` after 17a merges (no
  dependency on 17b or 17c).

17b, 17c, and 17d are independent of each other — all three only
depend on 17a's shell existing, not on one another — so they can be
built in any order (or in parallel) once 17a is merged, matching how
this project has sequenced independent sibling sub-phases before
(Phases 10-15 were each built directly from `main` once their shared
prerequisite work existed).

## Architecture: Shell Redesign (17a)

**New files**: `apps/web/src/components/Sidebar.tsx` (nav items +
bottom-pinned user name/sign-out) and `apps/web/src/components/Layout.tsx`
(composes `<Sidebar />` + a `<main>` content area). `App.tsx` shrinks
back to a pure route table wrapped in `<Layout>`, mirroring the
`Sidebar`/`Layout`/`App` split rather than growing the current
all-in-one `Layout` function inside `App.tsx`.

**Nav items** (flat list, no grouping): Documents, AI Chat, Legal
Draft, Tasks, Entities, Cases, Assistant, Settings — same `NavLink`
active-state styling as today, just rendered as a vertical list
instead of horizontal.

**User control**: display name + sign-out move from the current top
header into the bottom of `Sidebar`, matching Linear/Notion/Vercel-style
dashboards. The top header disappears entirely — pages get the full
viewport width minus the sidebar.

**Two new shared primitives**, used only by the 3 new pages:
- `Card.tsx`: names the bordered/padded container pattern the existing
  pages already inline ad hoc (e.g. `Tasks.tsx`'s
  `rounded border border-slate-200 bg-white`).
- `EmptyState.tsx`: centered message + optional action button, for "no
  cases yet" / "nothing linked yet" states.

Neither primitive is retrofitted onto the 5 existing pages in this
phase — see Scope.

## Architecture: Case Workspace UI (17b)

**`api.ts` additions** (same flat-file convention as every existing
addition — one interface + one thin function per endpoint, no new
per-domain file):
- `CaseOut { id, name, description, status, created_at }`
- `CaseDashboardOut extends CaseOut { documents: {id,title}[], tasks: {id,title,status}[], decisions: {id,summary}[] }`
- `DecisionOut { id, summary }` (new — backs the Decisions attach-picker)
- `listCases(): Promise<CaseOut[]>`
- `createCase(name, description?): Promise<CaseOut>`
- `getCase(id): Promise<CaseDashboardOut>`
- `updateCaseStatus(id, status): Promise<CaseOut>`
- `listDecisions(): Promise<DecisionOut[]>` (new, backs the picker)
- `attachDocumentToCase(documentId, caseId | null): Promise<{id, title}>`
- `linkTaskToCase(caseId, taskId): Promise<void>`
- `linkDecisionToCase(caseId, decisionId): Promise<void>`

**Backend addition**: `GET /decisions` in `services/api/src/api/decisions.py`,
scoped to the caller's own decisions (`Decision.user_id == current_user.id`,
admin sees all — same ownership pattern as the existing
`GET /decisions/{id}`), returning `id` + `summary` only (no supporting
documents — that's what the detail endpoint is for). Same shape as
`GET /tasks`'s existing scoping precedent.

**`Cases.tsx`** (route `/cases`): a card grid using `Card` — name,
status badge (`open`/`closed`), created date — each card links to
`/cases/:id`. A "New case" control follows `UploadDialog.tsx`'s exact
inline-toggle pattern (a button that swaps for an inline form with
name + optional description fields, Cancel to collapse back) — not a
new modal/dialog primitive. `EmptyState` renders when there are no
cases yet, with the same "New case" action.

**`CaseDetail.tsx`** (route `/cases/:id`): header with name,
description, and an open/closed toggle button calling
`updateCaseStatus`. Three `Card` sections — Documents, Tasks,
Decisions — each listing currently-linked items (title/summary + a
link to that item's own existing page, matching `Tasks.tsx`'s `Source
document` link convention) plus an inline attach control per section:
a `<select>` populated from `listDocuments()`/`listTasks()`/`listDecisions()`
filtered to items not already linked, with an "Attach" button calling
the matching link function and refreshing the dashboard afterward.

## Architecture: Manager Agent / Assistant UI (17c)

**`api.ts` additions**:
- `AskResponse { answer: string, tool_called: string | null }`
- `askManager(message: string): Promise<AskResponse>` calling
  `POST /manager/ask`.

**`Assistant.tsx`** (route `/assistant`): visually parallel to
`Chat.tsx` (a running list of exchanges, bubble styling, input + Send),
but functionally distinct: `/manager/ask` takes only `{ message }`, no
history — each submission sends just the current message. The local
turn list exists purely for on-screen readability; it is never sent
back to the backend (unlike `Chat.tsx`, which resends full visible
history every turn since `/chat` is stateless). When a response's
`tool_called` is non-null, render a small badge under that reply (e.g.
`via: search_documents`) — the point of this page is to make the
Manager Agent's tool selection observable, not just its final answer.

## Architecture: Personal AI Preferences / Settings UI (17d)

**`api.ts` additions**:
- `PreferencesOut { preferred_language: string | null }`
- `getPreferences(): Promise<PreferencesOut>` (`GET /preferences/me`)
- `setPreferences(preferredLanguage: string | null): Promise<PreferencesOut>` (`PUT /preferences/me`)

**`Settings.tsx`** (route `/settings`): one `<select>` — `No preference`
(→ `null`), `English`, `Nederlands`, `Deutsch` (matching this project's
existing Paperless OCR language footprint, `eng+nld+deu`) — plus a Save
button. Loads the current value via `getPreferences` on mount, persists
via `setPreferences` on save. Intentionally the only control on the
page today — the page exists so future settings have a home, not
because more exist to add right now.

## Error Handling & Loading Conventions

All three new pages follow the existing convention exactly, with no
new pattern introduced: `ApiError` caught and shown via
`<p className="text-sm text-red-600">{message}</p>`; a `loading`
boolean gating a `Loading…` placeholder; buttons disabled while a
request is in flight. Same as `Tasks.tsx`/`Chat.tsx` today.

## Testing

Matching this frontend's existing convention exactly: `api.test.ts`
only unit-tests the shared `request()` plumbing (auth headers,
content-type handling, error parsing) — individual per-domain
functions (`listTasks`, `chat`, etc.) and page components have no unit
tests today, and this phase does not introduce a new testing pattern
the codebase doesn't already have.

Final verification is live browser testing via the Playwright MCP
against the real running stack — the same practice used for every
prior frontend phase (5a–5c) — covering: sidebar navigation to all 8
pages, creating a case and attaching a real document/task/decision to
it, sending a message to the Assistant and seeing a `tool_called`
badge appear when a tool is invoked, and saving a language preference
and confirming it persists across a reload.

## Open Questions Resolved During Brainstorming

- **Which backend-only areas get UI**: Case Workspace, Manager Agent,
  Personal AI preferences — chosen over Planning Engine, Tool
  Registry/MCP, Knowledge Graph Decisions (beyond the attach-picker
  use), and Organizations/admin policies, which remain backend-only
  after this phase.
- **Manager Agent UI shape**: a separate `/assistant` page, not a mode
  toggle inside the existing Chat page — avoids conflating two
  functionally different backend capabilities (RAG+citations+memory
  vs. single-round tool-calling) in one UI.
- **Shell scope**: a full sidebar redesign, not just polishing the 3
  new pages within the existing top-nav shell — bigger change, touches
  every existing page's chrome (but not their internals).
- **Sidebar nav structure**: flat list, not grouped sections.
- **User control placement**: bottom of sidebar, top header removed
  entirely.
- **Implementation approach**: `Sidebar.tsx` + `Layout.tsx` extraction,
  plus two shared primitives (`Card`, `EmptyState`) used only by the 3
  new pages — not a full design-system retrofit of the existing 5
  pages.
- **Case detail attach flow**: included (documents, tasks, and
  decisions can all be attached directly from the Case detail page),
  requiring one small backend addition (`GET /decisions`) to make the
  three attach flows symmetric.
- **Delivery structure**: split into stacked sub-phases (17a shell,
  17b Cases, 17c Assistant, 17d Settings), matching this project's
  established convention for every other multi-capability phase,
  rather than one single Phase 17 PR.
