# ADR 0037: Phase 19 — Vehicles Page (List, Plate-Styled Lookup, Case Linking)

## Status
Accepted

## Context

Phase 18 (ADR 0036) built kenteken/VIN detection and RDW enrichment
entirely backend-only -- `lookup_vehicle` was reachable only via the
Manager Agent/MCP Tool Registry, with no REST endpoint and no frontend
page. This phase closes that gap with `/vehicles`, and additionally
lets vehicles link to Cases (Phase 16, ADR 0031) the same way
Documents/Tasks/Decisions already do. Full design rationale is in
`docs/superpowers/specs/2026-07-04-vehicles-page-design.md`.

## Decision

**A new `vehicles_router.py`** adds `GET /vehicles` (list, full RDW
payload) and `POST /vehicles/lookup` (direct REST wrapper around
Phase 18's `vehicle_agent.lookup_vehicle`) -- the first REST surface
for vehicle data. Both require only authentication, matching
`GET /entities`'s existing simplicity rather than duplicating the Tool
Registry's `vehicles.write` permission check.

**Vehicle↔Case linking reuses `graph_edges`**, identical to how
Task/Decision link to a Case: `POST /cases/{case_id}/vehicles/{vehicle_id}`.
Unlike Task/Decision linking, there's no ownership check on the vehicle
itself -- vehicles (like all entities) have no owner field.

**`LicensePlateInput.tsx`** is a real Dutch-plate-styled input (yellow
background, black bold text, blue "NL" band with EU stars) chosen over
a segmented multi-box input or a plain-input-plus-preview, confirmed
via a visual mockup comparison during brainstorming.

**`/vehicles`** shows this input plus a card-per-vehicle list, each
card distinguishing three states via `fetched_at`/`merk`: not yet
looked up, looked up but RDW had no match, or full RDW details.

**Built as one phase, not split into a/b sub-phases** like Phase
16->17b -- an explicit choice, even though it crosses backend and
frontend.

## Consequences

- **Deferred, not solved**: unlinking a vehicle from a case (Task/
  Decision have no unlink endpoint either); client-side kenteken
  format validation (RDW remains the sole source of truth); deleting a
  vehicle entity (no entity type in this codebase has a delete
  endpoint).
- Looking up a mistyped/nonexistent kenteken still permanently creates
  a `Vehicle`/`Entity` row with no RDW data (Phase 18's existing
  behavior, unchanged) -- the `/vehicles` list can accumulate "not
  found" entries over time from typos.
- No component-level test coverage was added for `Vehicles.tsx`/
  `LicensePlateInput.tsx` -- same reasoning as every prior frontend
  phase's ADR: this codebase has no React component testing library.
  Verified via `tsc -b` plus a live browser check.
