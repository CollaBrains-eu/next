# 0008: Phase 4 — Entity extraction & relationship graph

## Status
Accepted (2026-07-02)

## Context
Phase 4 is "case intelligence & entity graph" -- the `entity-agent` stub's
job. The actual graph *visualization* is explicitly Phase 5 scope
("frontend integration... graph view" in the phase plan); Phase 4 builds
the extraction, storage, and a queryable graph data API for that UI to
consume later, following the same agent pattern as the Planner Agent
(ADR 0004): an LLM call producing structured JSON, persisted, triggered
both on-demand and automatically via the existing workflow-trigger point.

Extraction quality was tested directly against `qwen2.5:3b-instruct`
before committing to this design (a realistic short legal-style
paragraph), and it reliably returns well-formed JSON with sensible entity
types and relationships -- no need to reach for a larger/different model.

## Decisions

### Schema: entities, mentions, relationships
- `entities` (id, name, entity_type, created_at) -- `entity_type` is one
  of `person | organization | location | other`, a free-form string with
  no DB enum (matches `documents.status`/`users.role`'s existing style in
  this codebase).
- `entity_mentions` (entity_id, document_id, unique together) -- which
  documents an entity appears in. No per-chunk granularity yet; that's
  more precision than anything currently consumes.
- `entity_relationships` (source_entity_id, target_entity_id,
  relationship_type, document_id) -- `relationship_type` is free-form text
  from the LLM (e.g. "represents", "opposing counsel"), not a fixed
  vocabulary. `document_id` records which document evidenced the
  relationship, for traceability.

### Deduplication: exact case-insensitive name+type match only
"John Smith" mentioned in two different documents resolves to one
`entities` row if the name (case-insensitively) and type match exactly.
No fuzzy matching, no LLM-based entity resolution ("J. Smith" vs "John
Smith" won't merge). This is a real, known limitation, not an oversight --
proper entity resolution is its own hard problem, and shipping something
useful now with an honest limitation beats blocking Phase 4 on solving
coreference resolution. Revisit if duplicate entities become a real
practical annoyance once there's enough real document volume to judge by.

### Relationships only reference entities from the same extraction
When parsing an extraction's `relationships` array, a relationship is
only kept if both its `source` and `target` names appear in that same
response's `entities` array (after resolution). This guards against the
model inventing a relationship to a name it didn't also list as an
entity -- defensive parsing, same spirit as the Planner Agent's
"skip anything that doesn't parse cleanly" behavior.

### Workflow trigger: same point as task extraction
`api/documents.py::_process_document` gains a second effect at
`status="ready"`, gated by `settings.auto_extract_entities_on_ready`
(default on): call the Entity Agent the same way it already calls the
Planner Agent. Kept as a fully separate LLM call (not merged into one
mega-prompt with task extraction) to keep each agent's prompt focused and
independently testable/tunable, matching how Legal/Planner/Document
agents are already separate modules rather than one do-everything agent.

### Graph query API
`GET /entities/{id}/graph` returns the entity plus its directly connected
neighbors and the edges between them (one hop, not full graph traversal)
-- exactly the shape a force-directed graph view (Phase 5) needs for
"show me what's connected to this entity," without over-building a
generic graph-traversal API before there's a real UI consumer to validate
the shape against.
