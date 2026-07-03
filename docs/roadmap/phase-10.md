# Phase 10 — Knowledge Graph 2

> **Status: done.** Built as one `Decision` node type and a generalized
> `GraphEdge` table (ADR 0025) -- scoped to this doc's own acceptance
> criteria (one new node/relationship, one real answerable question),
> not all ten node types proposed below. See `README.md` for the
> summary and ADR 0025 for what actually shipped vs. what this spec
> originally proposed. Kept here as historical context for how the
> open design questions got resolved.

## Goal

Grow the entity graph (ADR 0008: `Entity`, `EntityMention`,
`EntityRelationship` — people/organizations/locations, one-hop
neighborhoods) into a real knowledge graph spanning the system's other
first-class objects, so the AI can answer questions that span multiple
kinds of things, not just "who is connected to whom."

## Why now

The current graph answers "who/what is related to this entity." Once
Phase 8b (memory), 8c (plans), and 8d (reflection) exist, there's real
data worth graphing beyond people and documents: conversations,
decisions, tasks, workflows. A richer graph is what makes questions like
"which documents support this decision" or "which conversations were
about this case" answerable at all, instead of requiring a human to
manually trace the connection.

## New node types

In addition to the existing `Person`/`Organization`/`Document` (from
ADR 0008's `Entity.entity_type`):

```
Case
Conversation
Task
Workflow
Memory
Decision
Timeline
Vehicle
Property
Meeting
```

Some of these already exist as tables (`Task`, `Memory` from ADR 0018,
`Plan`/`PlanStep` from ADR 0019) — this phase is substantially about
*linking* existing rows into the graph, not creating all these as new
tables from scratch. `Case`, `Decision`, and `Meeting` are the genuinely
new concepts that need their own schema design.

## New relationship types

```
created
mentions
belongs_to
supports
contradicts
derived_from
assigned_to
summarizes
```

## Example questions this should make answerable

- "Which documents support this decision?" (`Decision` —derived_from→
  `Document`)
- "Which conversations were about this case?" (`Conversation`
  —belongs_to→ `Case`)
- "What tasks came out of this meeting?" (`Meeting` —created→ `Task`)

## Design questions to resolve before implementation

- **Schema**: does this stay in Postgres as more tables + a generalized
  edges table (extending `EntityRelationship`'s pattern), or does the
  graph's growing query complexity (multi-hop, multi-type traversal)
  justify a real graph database? ADR 0008 explicitly chose one-hop-only
  Postgres queries over a graph database for the original entity graph
  scope — this phase is exactly the point where that tradeoff should be
  re-examined, not assumed to still hold.
- **Multi-hop traversal**: the current `/entities/{id}/graph` is
  deliberately one-hop (ADR 0008), with the frontend re-centering on
  click to explore further. Does a real knowledge graph need actual
  multi-hop queries (e.g. "documents supporting decisions in this
  case"), and if so, does that change the one-hop-only API decision?
- **Node creation**: which of `created`/`mentions`/`derived_from`/etc.
  get populated automatically (e.g. by the Reflection Engine linking a
  `Decision` to the `Document`s it cited) versus require an explicit
  action?

## Acceptance criteria

- At least one new node type and relationship is real (backed by a
  table, not just a design doc) and queryable.
- At least one of the example questions above is answerable via a real
  API endpoint, verified against real data, not just a schema that
  supports it in principle.
