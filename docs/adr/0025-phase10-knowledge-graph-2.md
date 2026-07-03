# ADR 0025: Phase 10 — Knowledge Graph 2

## Status
Accepted

## Context

`docs/roadmap/phase-10.md` names ten new node types (Case, Conversation,
Task, Workflow, Memory, Decision, Timeline, Vehicle, Property, Meeting)
and eight relationship types, but its own acceptance criteria only ask
for one new node type and relationship, real and queryable, and one of
its example questions answerable end to end — not all ten types at
once. This ADR is that smallest safe slice.

## Decision

**One new node type: `Decision`.** Of the ten proposed, `Decision` is
the only one with no existing table to link into the graph (`Task` and
`Memory` already exist -- linking those in is separate future work, see
Consequences) and it's the one the roadmap's own headline example
question ("which documents support this decision?") is about.

**The real trigger is Plan approval, not a new UI action.** Phase 8c's
`POST /plans/{id}/approve` (ADR 0019) is the one place a human already
makes an actual decision in this codebase: approving a
`draft_legal_document`/`prepare_objection` plan is a decision to let
that draft leave the system. Creating a `Decision` row there reuses a
real, already-tested trigger instead of inventing a speculative new
"record a decision" endpoint nobody would call yet -- same reasoning
ADR 0004 used to scope the Legal Agent, reapplied here to scoping which
event creates a knowledge-graph node.

**A new generalized `graph_edges` table, not an extension of
`entity_relationships`.** ADR 0008's `entity_relationships` is
Entity-to-Entity only; `Decision`-to-`Document` is a genuinely
different pair of types. `graph_edges` (`source_type`, `source_id`,
`target_type`, `target_id`, `relationship_type`) is deliberately
polymorphic -- `source_id`/`target_id` have no DB-level foreign key
(can't reference two different tables from one column), a real
trade-off accepted for extensibility: adding a future node type
(`Conversation`, `Meeting`, ...) means adding rows, not a new join
table per type pair. This resolves `docs/roadmap/phase-10.md`'s open
schema question in favor of "more tables + a generalized edges table"
over introducing a real graph database -- the same low-blast-radius
call ADR 0002 made choosing Postgres/pgvector over Elasticsearch, and
ADR 0008 made choosing one-hop Postgres queries over a graph database,
reapplied here: a single new relationship doesn't justify a new
infrastructure dependency (a new service, ADR 0013's backup/restore
discipline extended to it, a new client library).

**`Decision` creation is a side effect of approval, wrapped in
try/except.** A failure to record the `Decision`/`graph_edges` rows
must never block the actual plan approval and execution -- the same
"side effect must never fail the primary flow" pattern used everywhere
else in this codebase (Signal notifications, 8b's memory
retrieval/creation, 8d's reflection). Approving a draft is the
important thing that happens; the graph node is bookkeeping about it.

**One new endpoint, `GET /decisions/{id}`**, returning the decision plus
every document connected to it via `graph_edges`
(`relationship_type="derived_from"`) -- directly answers "which
documents support this decision?", the roadmap's stated acceptance
criterion, without a generic cross-type graph-traversal endpoint this
phase doesn't need yet.

## Consequences

- **Deferred, not solved**: `Task`, `Memory`, `Plan` becoming graph
  nodes too; `Conversation`/`Workflow`/`Timeline`/`Vehicle`/`Property`/
  `Meeting` as new node types; multi-hop traversal (this phase is
  one-hop, same as ADR 0008's original entity graph); a real graph
  database. All of these are real future work `docs/roadmap/phase-10.md`
  names -- not done here because a single new relationship doesn't
  justify solving all of them speculatively.
- `graph_edges`'s lack of a DB-level foreign key on `source_id`/
  `target_id` means an orphaned edge (its source or target row deleted)
  is possible and not caught by the database. Acceptable for one
  relationship type today; worth revisiting (e.g. a cleanup job, or
  scoping `source_type`/`target_type` to an enum with per-type cascade
  logic in application code) once more relationship types accumulate.
- `Decision` is only created for the two approval-gated goal types.
  Other goals (`summarize_case`, `analyze_new_upload`,
  `organize_document_collection`, `generate_timeline`) never require
  approval and so never produce a `Decision` -- consistent with
  "approving is deciding," not a gap.
