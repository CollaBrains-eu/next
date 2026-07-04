# Phase 18: Vehicle Entity (Kenteken/VIN Detection + RDW Enrichment)

## Status
Approved (brainstorming)

## Context

Every phase since Phase 8c shipped from a fresh spec, not the original
roadmap (`docs/roadmap/`), which closed at Phase 15 (see README). Phase
16 added a `Case` node type; Phase 17 (17a-17d) caught the frontend up
on backend-only capabilities. This phase came out of a fresh
brainstorm: the user wants vehicle/license-plate data recognized in
documents, enriched from the RDW (Dutch vehicle authority) open data
API, and linked across documents that reference the same vehicle
(whether by kenteken, VIN, or both).

This is scoped deliberately narrow: **only** kenteken/VIN detection and
RDW enrichment. Other Dutch open-data sources (KVK company lookup,
PDOK, CBS, etc.) were raised in the same conversation but are
explicitly deferred to their own future phase, the same "split
multi-capability work" discipline this project already applies (Phase
16→17a-d).

## Decision

**A new `entity_type="vehicle"`, not a new top-level node type.** The
existing `Entity`/`EntityMention`/`EntityRelationship` machinery (Phase
4, ADR 0008) already does exactly what's needed here: `EntityMention`
already links an entity to every document that references it, so two
documents mentioning the same kenteken automatically share one
`Vehicle`'s entity row with zero new junction tables. It also means a
vehicle shows up for free in the existing `/entities` list and
one-hop graph view (Phase 5c) — no frontend work needed in this phase.

**A new `Vehicle` table holds the RDW payload, FK'd 1:1 to
`Entity.id`.** `Entity` itself only has `name`/`entity_type` — there's
nowhere to put structured data on it, and every other node type that
needs structured data (`Case`, `Decision`) already gets its own table
rather than bloating `Entity`. `Entity.name` is set to the kenteken
(formatted, e.g. `XX-99-XX`) when known, or the VIN when it isn't.

**Detection is pure regex, not LLM extraction.** Dutch kentekens follow
a small, fixed set of syntactic formats and VINs are a fixed 17-character
alphanumeric pattern (excluding I/O/Q) — a deterministic match is more
reliable and cheaper than asking the LLM, and avoids the 0/O, 1/I
confusion LLMs occasionally introduce on strict identifiers. This runs
as a new `vehicle_agent.py` step in the same document-processing event
chain (Phase 8a) as the existing LLM-based Entity Agent — alongside it,
not replacing it.

**RDW lookup is keyed on kenteken only.** The public RDW open data API
(opendata.rdw.nl, Socrata-based, "Gekentekende voertuigen" dataset plus
its fuel sub-dataset) does not expose VIN — that's private data, not
published. Used anonymously (no App Token yet) for this phase; the
client is written so a token can be added later via config without
changing its call sites.

**Dedup key is kenteken once known; VIN is a decoration, not an
independent global dedup key.** If a document contains both, they're
learned together onto one `Vehicle` row. If a document has only a VIN,
it's matched against existing VIN-only `Vehicle` rows (no kenteken
yet); if none match, a new VIN-only entity/vehicle is created. If a
kenteken for that same real-world vehicle later surfaces in a
different document, a second, separate `Vehicle`/`Entity` row is
created rather than merged — the exact same "no fuzzy resolution"
stance ADR 0008 already takes for person/organization entities, applied
consistently here.

**The same lookup function backs both the passive pipeline hook and an
active tool.** `lookup_vehicle(kenteken)` is registered in the existing
Tool Registry (Phase 9a) — no new endpoint, no new dispatch path. This
makes it automatically callable from the Manager Agent (`/manager/ask`,
Phase 11) and over MCP (Phase 9b), with zero additional wiring, and
guarantees the pipeline and the on-demand tool never drift into two
different lookup implementations.

**RDW fields** — an "extended" set (per the user's choice over just a
core identification set):
- Core: `kenteken`, `voertuigsoort`, `merk`, `handelsbenaming`,
  `eerste_kleur`, `datum_eerste_toelating`, `vervaldatum_apk`,
  `wam_verzekerd`, `openstaande_terugroepactie_indicator`,
  `brandstofomschrijving` (fetched from RDW's separate fuel-type
  sub-dataset, second query keyed on the same kenteken).
- Extended: `massa_ledig_voertuig`, `aantal_cilinders`, `wielbasis`,
  `catalogusprijs`, `aantal_zitplaatsen`, `aantal_deuren`,
  `vermogen_massarijklaar`, `lengte`, `europese_voertuigcategorie`.
- Plus `vin` (nullable) and `fetched_at` (timestamp of the RDW fetch).

**No auto-refresh.** RDW data is fetched once and stored; nothing
re-fetches it on a schedule. A user (or agent) can trigger a fresh
lookup later by calling the `lookup_vehicle` tool again, which
overwrites the stored fields and bumps `fetched_at`. This matches this
project's recurring "smallest safe slice" bias (e.g. ADR 0028's
Personal AI preferences: explicit, upserted, never expires on its
own).

## Data Flow

1. Document uploaded → OCR'd (existing pipeline, Phase 1b).
2. `vehicle_agent.detect_vehicles(text)` regex-scans the OCR'd text for
   kenteken and VIN patterns — runs as a new step in the same event
   chain the existing Entity Agent step already runs in (Phase 8a),
   not blocking or replacing it.
3. For each detected identifier (or pair): get-or-create a `Vehicle` +
   `Entity(entity_type="vehicle")` row per the dedup rule above, and a
   `EntityMention(entity_id, document_id)` row (reusing the existing
   table — this is what makes cross-document linking automatic).
4. If a kenteken is known for that vehicle and it has no `fetched_at`
   yet (i.e. never looked up), call `rdw_client.lookup(kenteken)` and
   populate the `Vehicle` row's RDW fields. A lookup failure (404,
   timeout, rate-limit, 5xx) is logged and swallowed — the entity/
   mention rows are already committed regardless, so document
   processing is never blocked by RDW availability.
5. Separately, `lookup_vehicle(kenteken)` (Tool Registry) does the same
   get-or-create + RDW-fetch, callable directly by a user via
   `/manager/ask` or MCP, with no document involved at all — useful for
   ad hoc lookups or manually retrying a vehicle that failed
   enrichment during pipeline processing.

## Error Handling

- RDW 404 (kenteken not found): the `Vehicle`/`Entity` row is still
  created (the identifier really was seen in a document, or a real
  kenteken the user asked about) but its RDW fields stay null.
  `fetched_at` is still set, so it's not retried automatically on every
  future document mentioning the same kenteken — a user has to
  explicitly re-trigger via the tool if they believe the 404 was
  transient (e.g. RDW registered the vehicle since).
- Network timeout / RDW 5xx / rate-limited: logged as a warning, same
  swallow-and-continue behavior — but `fetched_at` is deliberately
  **not** set on transient failures, so the next document mentioning
  this kenteken (or a manual tool call) will retry automatically. This
  distinguishes "RDW confirmed no such vehicle" from "we couldn't ask
  RDW" without adding a retry queue.
- No entity is created at all if regex detection produces zero matches
  in a document — this phase adds no vehicle-specific fields to
  `DocumentDetailOut` or any other response shape when nothing is
  found.

## Testing

Same practice as every backend phase in this project — `pytest`, no
live external calls in the suite:
- `vehicle_agent`'s regex detection: unit tests against known-valid and
  known-invalid kenteken/VIN strings (including OCR-noise cases like
  extra whitespace or lowercase).
- `rdw_client`: unit tests against a mocked `httpx` client covering
  success, 404, and timeout/5xx responses.
- The pipeline hook: an integration test uploading a document whose
  text contains a kenteken, asserting a `Vehicle`/`Entity`/
  `EntityMention` row exists afterward (RDW client mocked).
- The `lookup_vehicle` tool: a test calling it directly (bypassing
  `/manager/ask`'s tool-selection step, same pattern the existing tool
  tests use) and asserting the returned shape and persisted row.
- Cross-document linking: a regression test asserting two documents
  mentioning the same kenteken produce exactly one `Vehicle` row and
  two `EntityMention` rows.

## Open Questions Resolved

- **Standalone MCP server vs. in-codebase feature?** In-codebase, as a
  new entity type — the user wants this wired into the existing
  document pipeline and entity graph, not a separate service.
- **Detection: regex or LLM?** Regex — deterministic, free, and a
  better fit for identifiers with strict fixed formats.
- **RDW App Token?** None yet — anonymous access for this phase: lower
  rate limits are acceptable at this feature's expected volume. The
  client is written so a token can be added later via `.env` without
  call-site changes.
- **Passive-only or also an active/on-demand lookup?** Both — the same
  underlying function backs the pipeline hook and a Tool Registry
  entry, so it's usable from chat/Manager Agent and MCP with no extra
  wiring.
- **RDW field depth?** Extended set (see Decision section) over a
  minimal identification-only set.
- **VIN-kenteken merge if they surface in separate documents?** Not
  attempted — explicitly deferred, consistent with ADR 0008's existing
  "no fuzzy resolution" stance for entities generally.

## Consequences

- **Deferred, not solved**: other Dutch open-data sources (KVK, PDOK,
  CBS, Kadaster) raised in the same brainstorm are out of scope for
  this phase entirely — candidate future phases, each getting its own
  spec. No frontend UI is added in this phase either (mirrors Phase
  16's backend-first, UI-later pattern with Phase 17b) — a vehicle is
  visible today only via the existing `/entities` list/graph view and
  the Manager Agent tool, not a dedicated page.
- VIN-only vehicles that later turn out to share a kenteken with an
  existing vehicle produce a second, separate entity rather than a
  merge — a known, accepted limitation, not a bug, matching this
  project's existing entity-resolution philosophy.
- RDW data can go stale (an APK renewal, insurance lapsing) since there
  is no auto-refresh — acceptable for this phase; a scheduled refresh
  is a candidate future addition if it turns out to matter in
  practice.
