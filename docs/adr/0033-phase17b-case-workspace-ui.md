# ADR 0033: Phase 17b — Case Workspace UI

## Status
Accepted

## Context

Phase 16 shipped the Case Workspace backend (Case CRUD, document/task/
decision linking, dashboard endpoint) with no UI at all. Phase 17
(`docs/superpowers/specs/2026-07-04-frontend-catchup-design.md`) closes
that gap alongside two other backend-only areas. 17a merged first and
built the sidebar shell, `Card`, and `EmptyState` primitives this
sub-phase builds on.

## Decision

**Add `GET /decisions`, a list endpoint scoped to the caller's own
decisions.** No such endpoint existed before this phase — only
`GET /decisions/{id}` — and it's needed to populate the Decisions
attach-picker on the Case detail page. Returns just `id` + `summary`
(no `supporting_documents`), unlike the detail endpoint's `DecisionOut`,
since a list view has no use for the join and it would be wasted work
per row.

**Attach flows reuse `UploadDialog.tsx`'s inline-toggle pattern**, not
a new modal/dialog primitive: each of the three sections (Documents,
Tasks, Decisions) on the Case detail page has an "+ Attach" button that
swaps for an inline `<select>` (filtered to items not already linked)
plus an Attach/Cancel pair, matching how "New case" and the existing
upload flow already work in this codebase.

**One new sidebar nav item ("Cases")**, added to the flat list Phase
17a built. No further shell changes.

## Consequences

- **Deferred, not solved**: UI for Planning Engine, Tool Registry/MCP,
  Organizations/admin policies, and Learning dataset export remain
  backend-only — outside this phase's scope entirely (see the Phase 17
  spec).
- The Decisions/Tasks/Documents attach-pickers use `listDocuments()`/
  `listTasks()`/`listDecisions()` with their default page sizes (e.g.
  `GET /tasks`'s default `limit=50`) — a pre-existing pagination
  limitation of those endpoints, not something this phase changes. On
  an account with more than the default page size of unlinked items,
  the picker won't show all of them. Not fixed here since `Tasks.tsx`
  itself already has this same limitation.
- No component-level test coverage was added for `Cases`/`CaseDetail` —
  same reasoning as 17a's ADR: this codebase has no React component
  testing library. Verification is `tsc -b` typecheck plus a live
  browser check.
