# ADR 0036: Phase 18 — Vehicle Entity (Kenteken/VIN Detection + RDW Enrichment)

## Status
Accepted

## Context

This phase came from a fresh brainstorm, not the original roadmap
(closed at Phase 15) or Phase 16/17's own follow-ups: the user wants
vehicle/license-plate data recognized in documents, enriched from the
RDW (Dutch vehicle authority) open data API, and linked across
documents referencing the same vehicle. Full design rationale is in
`docs/superpowers/specs/2026-07-04-vehicle-entity-design.md`.

## Decision

**A new `entity_type="vehicle"`, not a new top-level node type.** The
existing `Entity`/`EntityMention`/`EntityRelationship` machinery (Phase
4, ADR 0008) already links an entity to every document mentioning it,
so two documents mentioning the same kenteken automatically share one
entity -- no new junction tables, and the vehicle shows up for free in
the existing `/entities` list and one-hop graph view (Phase 5c).

**A new `Vehicle` table holds the RDW payload**, FK'd 1:1 to
`Entity.id` -- the same pattern `Case`/`Decision` already use for
structured data `Entity` itself has no columns for.

**Detection is pure regex** (`api/vehicle_agent.py`), not LLM
extraction -- kentekens and VINs follow small, fixed syntactic formats,
which a deterministic pattern matches more reliably (and for free) than
an LLM prompt, avoiding the 0/O, 1/I confusion LLMs occasionally
introduce on strict identifiers. Runs alongside the existing LLM-based
Entity Agent in the same document-processing event chain (Phase 8a),
not replacing it.

**RDW lookup (`api/rdw_client.py`) is keyed on kenteken only** --
VIN isn't in RDW's public dataset (privacy). Used anonymously (no App
Token yet); written so a token can be added later via config with no
call-site changes. Field names were verified against a real live
record during implementation (kenteken `TT249H`) -- one originally
planned field, `lengte`, turned out not to exist on this dataset at all
and was dropped from the fetch list (the `Vehicle.lengte` column stays
in the schema, harmlessly always null, rather than a second migration
just to remove it).

**Dedup key is kenteken once known**; VIN is a secondary field. A
VIN-only vehicle that later turns out to share a kenteken with an
existing vehicle produces a second, separate row rather than a merge --
the same "no fuzzy resolution" stance ADR 0008 already takes for
person/organization entities.

**One shared function backs both the passive pipeline hook and an
active tool.** `lookup_vehicle` is registered in the Tool Registry
(Phase 9a), automatically callable from the Manager Agent
(`/manager/ask`, Phase 11) and MCP (Phase 9b) with zero additional
wiring.

**No auto-refresh.** RDW data is fetched once (`fetched_at` records
when); a fresh fetch only happens via an explicit `lookup_vehicle` tool
call.

## Consequences

- **Deferred, not solved**: other Dutch open-data sources (KVK, PDOK,
  CBS, Kadaster) raised in the same brainstorm are out of scope --
  candidate future phases, each getting its own spec. No frontend UI is
  added this phase either -- a vehicle is visible today only via the
  existing `/entities` list/graph view and the Manager Agent tool.
- VIN-only vehicles that later turn out to share a kenteken with an
  existing vehicle produce a second, separate entity rather than a
  merge -- accepted, not a bug.
- RDW data can go stale (APK renewal, insurance lapsing) since there's
  no auto-refresh -- acceptable for this phase; a scheduled refresh is
  a candidate future addition if it turns out to matter in practice.
- The regex-based kenteken detection covers the commonly-used NL
  sidecode formats, not an exhaustive historical list -- a documented,
  accepted limitation, not a bug.
- `Vehicle.lengte` is a schema column with no data source feeding it --
  RDW's public dataset doesn't publish vehicle length under this
  dataset. Left in place rather than removed via a second migration;
  harmless since it's nullable.
