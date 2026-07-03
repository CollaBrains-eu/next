# ADR 0031: Phase 16 — Case/Matter Workspace

## Status
Accepted

## Context

Phase 16 is the first phase with no pre-written roadmap entry -- the
original 15-phase roadmap (`docs/roadmap/`) is complete as of Phase 15.
This direction came from brainstorming with the user rather than a
pre-existing spec (`docs/superpowers/specs/2026-07-03-case-workspace-design.md`).

The word "case" already appears in this codebase without a persistent
concept behind it: Planning Engine's `summarize_case` goal type (Phase
8c, ADR 0019) and `Decision`'s own docstring (Phase 10, ADR 0025) both
assume a notion of "case" that was never given a real, addressable
identity. Everywhere else, work is organized around loose, ad hoc
references -- a raw `document_ids` list passed into a goal, no
persistent grouping of the tasks or decisions that come out of that
work.

## Decision

**A new `Case` table, user-scoped, with optional membership
everywhere.** A document, task, or decision can exist with no case at
all, exactly as before this phase -- no migration backfill, no
existing-row risk. This is the same "smallest safe slice" bias ADR
0004 established for the Legal Agent, reapplied to a new data model:
add the concept without forcing every existing row through it.

**`Document.case_id` is a direct FK; `Task`/`Decision` link via the
existing polymorphic `graph_edges` table (Phase 10, ADR 0025).**
Documents are the most central, most-queried relationship, so a plain
column keeps that query simple and gets real DB-level referential
integrity (`ON DELETE SET NULL`). Tasks and decisions reuse
`graph_edges` (`relationship_type="belongs_to"`) instead of adding two
more nullable FK columns -- exactly the extensibility `graph_edges` was
built for in ADR 0025 ("adding a future node type means adding rows,
not a new join table per type pair").

**`summarize_case` accepts a `case_id` in addition to `document_ids`,
with `case_id` taking precedence if both are given.** `create_plan()`
resolves `case_id` to that case's document list before calling
`build_steps()`, which is unmodified and stays synchronous -- the
resolution happens in the one place that already has `db` access and is
already `async`. This is the concrete proof that a real `Case` is
useful, not just new structure sitting unused.

## Consequences

- **Deferred, not solved**: case-level sharing or collaboration between
  multiple users (this overlaps Phase 14 (ADR 0029)'s still-open
  tenant/access-control work, not reopened here); automatic case
  detection or clustering of documents (no signal in this codebase
  today would make that reliable -- cases are created explicitly by a
  user, the same explicit-over-inferred bias Phase 13 (ADR 0028)
  established for preferences); a status workflow beyond a plain
  `open`/`closed` flag (no archival policy, no closing checklist).
- Entities and memories remain document/user-scoped, not case-scoped --
  case membership was deliberately limited to documents, tasks, and
  decisions to keep this slice contained.
- `graph_edges` rows linking a task/decision to a case have no DB-level
  cascade (the same accepted tradeoff ADR 0025 made) -- deleting a
  `Case` deletes its `graph_edges` rows explicitly in application code
  before deleting the case itself, so no orphaned edges point at a
  deleted case.
