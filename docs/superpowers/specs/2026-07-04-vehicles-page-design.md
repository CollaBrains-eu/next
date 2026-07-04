# Phase 19: Vehicles Page (List, Plate-Styled Lookup, Case Linking)

## Status
Approved (brainstorming)

## Context

Phase 18 (ADR 0036) built the `entity_type="vehicle"` backend -- passive
kenteken/VIN detection during document processing, RDW enrichment, and
a `lookup_vehicle` tool reachable only through the Manager Agent
(`/manager/ask`) and MCP. It was deliberately backend-only: no REST
endpoint, no frontend page. This phase closes that gap with a `/vehicles`
page, following the same "backend first, UI later" pattern Phase 16 ->
17b already established for Cases.

During brainstorming this grew beyond "just a styled input": the user
wants vehicles linkable to Cases too, the same way Documents/Tasks/
Decisions already are (Phase 16, ADR 0031). That requires backend
additions (a `Vehicle` <-> `Case` link, a vehicles list endpoint, a
direct lookup endpoint) alongside the frontend page. Explicitly built
as **one single phase**, not split into a/b sub-phases -- the user's own
choice, even though the scope crosses backend and frontend.

## Decision

**A dedicated `vehicles_router.py`**, not folded into `entities.py` or
`cases_router.py` -- one clear responsibility per file, matching this
project's established convention (`cases_router.py` for Case endpoints,
`entities.py` for Entity endpoints).

**`GET /vehicles`** lists every `Vehicle` row with its full RDW payload
(kenteken, merk, handelsbenaming, voertuigsoort, eerste_kleur,
datum_eerste_toelating, vervaldatum_apk, wam_verzekerd,
openstaande_terugroepactie_indicator, brandstofomschrijving,
fetched_at). Global/unscoped, same as the existing `GET /entities` --
vehicles have no owner (Entity never has, Phase 4 ADR 0008).

**`POST /vehicles/lookup`** (body `{kenteken: str}`) is a direct REST
wrapper around Phase 18's `vehicle_agent.lookup_vehicle`, the same
"thin REST wrapper alongside the Tool Registry entry" pattern
`/documents/{id}/extract-entities` already uses for `extract_entities`.
Always returns a row, even when RDW has no match for the kenteken --
Phase 18's existing "confirmed not found still creates the row"
behavior is unchanged here, not revisited.

**Vehicle<->Case linking reuses `graph_edges`** exactly like Task/
Decision did in Phase 16: `POST /cases/{case_id}/vehicles/{vehicle_id}`
creates a `GraphEdge(source_type="vehicle", source_id=vehicle.id,
target_type="case", target_id=case.id, relationship_type="belongs_to")`.
`CaseDashboardOut` gains a `vehicles: list[CaseVehicleOut]` field
(`id`, `kenteken`, `merk`, `handelsbenaming`); `get_case_dashboard()`
queries vehicle edges the same way it already queries task/decision
edges. **Unlike task/decision linking, the link endpoint only checks
Case ownership, not Vehicle ownership** -- vehicles have no owner
concept to check (same reasoning as `Entity` never having one).

**`LicensePlateInput.tsx`** is a new, reusable component: a single
controlled text input styled as a real Dutch plate (yellow background,
black bold uppercase text, blue left band with "NL" + EU stars) --
Option A from the brainstorm's visual comparison, chosen over a
segmented multi-box input or a plain-input-plus-preview. Typed text is
uppercased automatically; no client-side format validation --
RDW/`lookup_vehicle` is the source of truth for whether a kenteken is
real, the same "let the backend validate" bias this project already
applies elsewhere (e.g. Legal Draft never client-validates instruction
content).

**`Vehicles.tsx`** (new `/vehicles` route + sidebar item) renders the
`LicensePlateInput` plus a "Zoek op" button above a `Card`-per-vehicle
list (`GET /vehicles` on mount, refetched after every successful
lookup -- same `refresh()` pattern `CaseDetail.tsx` already uses).
Each card shows one of three states, distinguished by `fetched_at`/
`merk` exactly as Phase 18's data model already supports:
- `fetched_at` is null -> "Nog niet opgehaald"
- `fetched_at` set, `merk` null -> "Geen RDW-gegevens gevonden voor dit kenteken"
- `merk` set -> merk, handelsbenaming, voertuigsoort, eerste_kleur,
  vervaldatum_apk, wam_verzekerd rendered plainly

**`CaseDetail.tsx` gets a fourth attach-flow section (Vehicles)**,
identical in shape to the existing Documents/Tasks/Decisions sections
-- same `AttachControl` inline toggle-to-`<select>` pattern, same
`attachOptions`/`linkedIds` filtering logic, extended to a fourth
`AttachSection` variant rather than duplicated.

## Data Flow

1. User opens `/vehicles`: `listVehicles()` (`GET /vehicles`) populates
   the card list.
2. User types a kenteken into `LicensePlateInput` and clicks "Zoek op":
   `lookupVehicle(kenteken)` (`POST /vehicles/lookup`) runs the real
   RDW call server-side (via Phase 18's existing `vehicle_agent.lookup_vehicle`,
   unchanged), the list is refetched, and the new/updated vehicle's
   card reflects the result.
3. On `/cases/:id`, the Vehicles section's "+ Attach" control lists
   vehicles not yet linked to this case (from the same `listVehicles()`
   call `Vehicles.tsx` uses); selecting one and clicking Attach calls
   `linkVehicleToCase(caseId, vehicleId)` (`POST /cases/{case_id}/vehicles/{vehicle_id}`)
   and refreshes the case dashboard.

## Error Handling

- `POST /vehicles/lookup` with a kenteken RDW doesn't recognize: not an
  error response -- 200 with a vehicle row whose RDW fields are all
  null (Phase 18's existing "confirmed not found" path). The frontend
  shows the "Geen RDW-gegevens gevonden" card state, not an error
  banner.
- `POST /vehicles/lookup` during a genuine RDW outage (timeout/5xx):
  Phase 18's `RdwLookupError` propagates up; the endpoint returns a
  502 (external dependency failure), and `Vehicles.tsx` shows an inline
  error message near the input, same style as other pages' `ApiError`
  handling (e.g. `Settings.tsx`).
- `POST /cases/{case_id}/vehicles/{vehicle_id}` with an unknown
  `vehicle_id`: 404, mirroring `link_task_endpoint`/`link_decision_endpoint`'s
  existing behavior for unknown task/decision IDs.

## Testing

Same practice as every prior phase -- `pytest` for the backend
(mocked RDW, no live calls in the suite), `tsc -b` + `pnpm test` +
a live Playwright browser check for the frontend (no React component
testing library in this codebase, unchanged since Phase 17a's ADR):
- `vehicles_router.py`: list/lookup/link endpoints, including the
  "link fails with 404 on an unknown vehicle_id" and "RDW outage
  surfaces as 502" cases.
- `cases.py`: `link_vehicle_to_case` and the extended
  `get_case_dashboard` (vehicles included alongside tasks/decisions).
- Frontend: `tsc -b` typecheck plus a real browser walk-through --
  looking up a kenteken on `/vehicles`, seeing it appear in the list,
  and attaching it to a case from `/cases/:id`.

## Open Questions Resolved

- **Kenteken input style?** Option A -- a single plate-styled input you
  type directly into (chosen over segmented boxes or a plain-input-
  plus-preview), confirmed via the visual companion mockup.
- **What does the vehicle list show?** Full RDW details per card, not
  just kentekens.
- **Case linking now or later?** Now, as part of this same phase --
  the user's explicit choice, even though it pulls in backend work.
- **Split into sub-phases like 16->17b?** No -- built as one phase,
  the user's explicit choice.

## Consequences

- **Deferred, not solved**: unlinking a vehicle from a case (matching
  Task/Decision, which also have no unlink endpoint today); any
  client-side kenteken format validation (RDW is the sole source of
  truth); a scheduled RDW re-fetch for stale data (still Phase 18's
  original deferral, unchanged).
- Looking up a typo'd/nonexistent kenteken still permanently creates a
  `Vehicle`/`Entity` row with no RDW data (Phase 18's existing
  behavior) -- the `/vehicles` list can accumulate "not found" entries
  from mistyped lookups over time. Not addressed here; a candidate
  future addition would be letting a user delete a vehicle entity, the
  same gap Entities in general already have (no delete endpoint exists
  for any entity type).
- Vehicle linking has no ownership check beyond the Case itself, since
  vehicles (like all entities) have no owner -- any authenticated user
  who owns the case can attach any vehicle in the system to it, the
  same trust model already implicit in how Entities are globally
  shared and unscoped.
