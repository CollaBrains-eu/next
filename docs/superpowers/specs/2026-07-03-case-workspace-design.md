# Phase 16 — Case/Matter Workspace: Design

## Status
Draft, pending final user sign-off before implementation.

## Context

CollaBrains' original 15-phase roadmap (`docs/roadmap/`, ADRs 0001-0030)
is complete. This is the first phase without a prior roadmap document
naming it — a genuinely new direction chosen through brainstorming
rather than a pre-written spec, following the discipline
`docs/roadmap/README.md` asks any future phase to use.

Everywhere in the current system, work is organized around loose,
ad hoc references: Planning Engine goals take a raw `document_ids`
list; `Decision` (Phase 10, ADR 0025) links to the documents it was
derived from but not to any persistent case; the entity graph has no
case scoping at all. The word "case" already appears in the codebase
without a concept behind it — Planning Engine's `summarize_case` goal
type (Phase 8c) and `Decision`'s own docstring ("a case") both assume a
notion of "case" that was never built as a real, addressable thing.

## Goal

A persistent `Case` that documents, tasks, and decisions can belong to,
with a single endpoint that assembles all three into one dashboard view
— closing the gap between what several existing features already imply
and what actually exists as data.

## Scope

**In scope**: `Case` CRUD; attaching/detaching documents; linking
existing tasks and decisions to a case; a case-detail endpoint
assembling all three; extending Planning Engine's `summarize_case` goal
to optionally resolve its document list from a `case_id`.

**Explicitly out of scope, not attempted here**:
- Case-level sharing or collaboration between multiple users — this
  overlaps with Phase 14 (Enterprise)'s still-open tenant/access-control
  work (ADR 0029) and isn't reopened by this phase.
- Automatic case detection or clustering of documents — no signal in
  this codebase today would make that reliable; cases are created
  explicitly by a user, the same explicit-over-inferred bias Phase 13
  (ADR 0028) already established for preferences.
- Case status workflow beyond a simple `open`/`closed` flag — no
  archival policy, no closing checklist.
- Entities and memories remain document/user-scoped, not case-scoped.

## Data Model

**`Case`** (new table):
- `id` (UUID, PK)
- `user_id` (FK → `users.id`) — the owner; same per-user scoping as
  `Document`/`Plan`/`Decision` today, not organization-scoped (Phase 14
  is a foundation only, per ADR 0029 — not reopened here)
- `name` (String, required)
- `description` (Text, nullable)
- `status` (String, default `"open"`; `"open"` or `"closed"`)
- `created_at`

**`Document.case_id`** (new nullable column): FK → `cases.id`,
`ON DELETE SET NULL`. Purely additive — every existing document has
`case_id = NULL` and behaves exactly as before this phase. No migration
backfill needed (unlike Phase 14's `User.organization_id`, this is
optional from day one).

**Task/Decision → Case linking**: via the existing polymorphic
`GraphEdge` table (Phase 10, ADR 0025) — `relationship_type="belongs_to"`,
`source_type="task"|"decision"`, `source_id=<task/decision id>`,
`target_type="case"`, `target_id=<case id>`. No schema changes to
`tasks` or `decisions`. This reuses the exact mechanism ADR 0025 built
for "adding a future node type means adding rows, not a new join table
per type pair."

## API Surface

- `POST /cases` — create (`name`, `description`). Starts `status="open"`.
- `GET /cases` — list the caller's own cases.
- `GET /cases/{id}` — the case dashboard: case fields + documents
  (queried by `case_id`) + tasks and decisions (queried by `GraphEdge`,
  `target_type="case"`, `target_id=<id>`, `relationship_type="belongs_to"`).
- `PATCH /cases/{id}` — update `name`, `description`, and/or `status`
  (`"open"`/`"closed"`). The only way `status` ever changes after
  creation — without this endpoint the field would be write-once and
  meaningless.
- `DELETE /cases/{id}` — deletes the case. Linked documents' `case_id`
  becomes `NULL` automatically (FK `ON DELETE SET NULL`); linked
  task/decision `GraphEdge` rows are deleted explicitly in application
  code first (no DB-level cascade for the polymorphic table — the same
  accepted tradeoff ADR 0025 already made).
- `PUT /documents/{document_id}/case` — body `{"case_id": UUID | null}`.
  Attaches, moves, or detaches (`null`) a document. Overwrites silently
  if already attached elsewhere — not an error.
- `POST /cases/{case_id}/tasks/{task_id}` — link an existing task to a
  case (creates the `GraphEdge`). Validates the task and case share the
  same owner (or caller is admin) before linking.
- `POST /cases/{case_id}/decisions/{decision_id}` — same, for decisions.

Ownership: only the case's `user_id` (or `admin`) can view or modify
it, matching the existing `Document`/`Plan`/`Decision` pattern exactly.

## Planning Engine Integration

`planning_engine.py`'s `summarize_case` goal (Phase 8c) currently
requires `goal_params = {"document_ids": [...]}`. This phase extends it
to also accept `goal_params = {"case_id": ...}`: when given a `case_id`,
`build_steps()` resolves the document list by querying
`Document.case_id == case_id` before building the same one-step-per-document
template it already produces. Both call shapes are supported —
existing callers passing `document_ids` directly are unaffected. If a
caller somehow provides both, `case_id` takes precedence and
`document_ids` is ignored (documented in the function's docstring, not
silently merged or summed) — this should not come up in practice since
the frontend/caller picks one mode, but the precedence is made explicit
rather than left ambiguous.

This is the one piece of proof, beyond CRUD, that a real `Case` is
useful and not just new structure sitting unused.

## Error Handling

- Creating a case with an empty `name`: `422` (Pydantic validation).
- Linking a task/decision that doesn't exist, or belongs to a different
  user (and caller isn't admin): `404`/`403` as appropriate, mirroring
  existing endpoints' conventions exactly (e.g. `decisions.py`'s
  ownership check).
- Attaching a document that belongs to a different user to someone
  else's case: `403`.
- All new endpoints require authentication (`get_current_user`); no new
  auth pattern introduced.

## Testing

- Unit tests: `Case` CRUD, document attach/detach/move, task/decision
  linking (success + cross-user rejection), case deletion correctly
  nulling `Document.case_id` and removing `GraphEdge` rows.
- HTTP round-trip tests: full `GET /cases/{id}` dashboard assembly with
  real linked documents/tasks/decisions; ownership scoping (a second
  user cannot view/modify another's case); missing-auth rejection.
- Planning Engine integration test: `create_plan(goal_type="summarize_case",
  goal_params={"case_id": ...})` produces the identical step list as
  passing the same documents' IDs directly via `document_ids`.

## Migration

One new table (`cases`), one new nullable column
(`documents.case_id`). No backfill, no existing-row risk — unlike
Phase 14's `User.organization_id`, every pre-existing document already
satisfies `case_id IS NULL` by definition. This is one of the lowest-risk
migrations in the project's history, not one of the highest.

## Open Questions Resolved During Brainstorming

- **Scope of what a Case groups**: Documents + Tasks + Decisions, not
  entities/memories (keeps the slice contained; those can be added
  later if a real need for case-scoped entities/memories emerges).
- **Mandatory vs. optional membership**: optional — no migration risk,
  consistent with this project's established "smallest safe slice"
  bias.
- **Linking mechanism**: hybrid — direct `case_id` FK on `Document`
  (the most central, most-queried relationship), `GraphEdge` reuse for
  the secondary Task/Decision links.
- **Planning Engine integration**: included in this slice rather than
  deferred, since it's small and is the clearest demonstration that
  `Case` is actually useful.
