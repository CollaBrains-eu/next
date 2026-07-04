# ADR 0032: Phase 17a — Sidebar Shell Redesign

## Status
Accepted

## Context

Every backend phase since 8c shipped API-only with no frontend UI, and
Phase 17 (`docs/superpowers/specs/2026-07-04-frontend-catchup-design.md`)
closes the highest-value slice of that gap: UI for Case Workspace,
the Manager Agent, and Personal AI preferences. Alongside those three
pages, the user explicitly asked during brainstorming for the overall
app shell to feel more like a polished enterprise SaaS product rather
than the existing bare top-nav layout.

Phase 17 is split into stacked sub-phases (17a-17d), the same pattern
this project has used for every other multi-capability phase (1a/1b,
5a/5b/5c, 9a-9d). This ADR covers 17a only: the shell itself. 17b/17c/17d
each build one new page on top of it and are not touched here.

## Decision

**Replace the top nav with a persistent left sidebar**, matching
Linear/Notion/Vercel-style dashboards: nav items rendered as a vertical
list instead of horizontal, with the user's display name and sign-out
control pinned at the bottom of the sidebar instead of a separate top
header. The top header is removed entirely — pages get the full
viewport width minus the sidebar.

**`App.tsx` shrinks to a pure route table.** The chrome (sidebar +
content area) moves into a new `Layout` component, which composes a
new `Sidebar` component. This mirrors the one-responsibility-per-file
convention already established elsewhere in this codebase (e.g.
`Tasks.tsx` only handles tasks) — before this change, `App.tsx` did
both routing and all of the shell's markup in one file.

**Two new shared primitives (`Card`, `EmptyState`) are added now with
no consumer yet in this sub-phase.** `Card` just names the
bordered/padded container pattern the existing pages already inline ad
hoc; `EmptyState` is a centered message + optional action, for "no
cases yet" style states. 17b's Case Workspace UI is their first real
consumer. This is a deliberate, narrow exception to this project's
usual "don't build things nothing uses yet" bias — justified because
this sub-phase's entire purpose is to prepare the shell for the three
pages stacked on top of it.

**Nav items in this sub-phase are only the 5 that already exist**
(Documents, AI Chat, Legal Draft, Tasks, Entities) — Cases, Assistant,
and Settings are deliberately NOT added to the sidebar yet, since those
pages don't exist until 17b/17c/17d merge. Adding the links now would
ship three dead links pointing at the `NotFound` catch-all route.

**The sidebar renders on every route, including `/login`**, matching
the exact behavior of the header it replaces (the current top nav
already renders regardless of auth state; `HeaderUser` simply renders
nothing when there's no user). This wasn't a requirement to preserve —
just not something this phase set out to change.

## Consequences

- **Deferred, not solved**: UI for Planning Engine, Tool Registry/MCP,
  Knowledge Graph Decisions (beyond what 17b's attach-picker needs),
  Organizations/admin policies, and Learning dataset export all remain
  backend-only after Phase 17 entirely — only Case Workspace, Manager
  Agent, and Personal AI preferences get UI in this phase, per the
  spec's explicit scope choice.
- No component-level test coverage was added for `Sidebar`/`Layout` —
  this codebase has no React component testing library (`vitest` only
  covers the plain-function `api.ts` request layer), and this phase
  doesn't introduce one. Verification is `tsc -b` typecheck plus a live
  browser check against the real running stack, the same practice used
  for every prior frontend phase (5a-5c).
- Grouped/sectioned sidebar nav (e.g. "Workspace" vs "AI" groupings)
  was considered and explicitly rejected in favor of a flat list — with
  8 total items once 17b/c/d ship, a flat list stays legible without
  needing section headers.
