# 0046 — Don't persist a vehicle when RDW confirms it doesn't exist

## Status

Accepted

## Context

`vehicle_agent.py`'s regex-based kenteken/VIN detection is deliberately
loose (ADR: covers the common NL sidecode formats, not exhaustive) — a
false-positive regex match on garbage OCR text was always possible.
Previously, `_get_or_create_vehicle_entity` created the `Entity`+`Vehicle`
row immediately on any detected kenteken, *before* checking RDW, and
`_enrich_from_rdw` ran afterward purely to fill in fields — a confirmed
"not found" from RDW just set `fetched_at` on the already-persisted row
and left it there permanently. Every false-positive regex match became a
permanent garbage row.

## Decision

- New `_get_or_create_validated_vehicle()` in `vehicle_agent.py`: for a
  kenteken not already known in the DB, RDW is checked *before* anything
  is created. A confirmed not-found (`fetch_vehicle_data` returns `None`)
  returns `None` — nothing persisted. A transient RDW failure
  (`RdwLookupError`) still creates an unenriched row for later retry,
  preserving the existing retry-later design intent (`_enrich_from_rdw`'s
  docstring) — only a *confirmed* absence blocks creation, not "RDW is
  down right now."
- Kentekens already known in the DB skip this gate entirely (existing
  `_enrich_from_rdw` retry-if-not-yet-fetched path, unchanged) — a
  kenteken RDW previously confirmed real doesn't get re-validated on
  every subsequent document mention.
- `lookup_vehicle()` (the manual/tool-invoked path, force-refresh
  semantics) rewritten to call RDW *before* creating/updating anything.
  Returns `None` for a brand-new kenteken RDW doesn't recognize. An
  **already-known** vehicle is never deleted or hidden just because RDW
  later reports not-found for it on a force-refresh — a previously-valid
  plate having RDW report "not found" today is far more likely a
  transient/data-quality hiccup on RDW's side than proof the vehicle
  stopped existing, so the existing row is left untouched and returned
  as-is rather than treated as absent.
- `lookup_vehicle`'s return type changed from `Vehicle` to `Vehicle |
  None`. Both callers updated: the Tool Registry handler
  (`tools.py::_lookup_vehicle_handler`) now catches `RdwLookupError` and
  reports `{"found": false, "error": ...}` gracefully (previously this
  couldn't happen — the exception used to be swallowed inside
  `lookup_vehicle` itself); the REST endpoint
  (`vehicles_router.py::lookup_vehicle_endpoint`) now returns `404` for
  `None` instead of a `200` with a near-empty vehicle body.

## Consequences

- False-positive kenteken regex matches on documents no longer leave
  permanent garbage `Entity`/`Vehicle` rows.
- `POST /vehicles/lookup` callers (frontend, MCP tools) must now handle
  `404` as a real "not found" response, not just `502` for outages.
- VIN-only detections are unaffected — there's no RDW-by-VIN lookup to
  gate on, so they're created exactly as before.

## Verification

- New tests in `test_vehicle_agent.py`: not-found new kenteken persists
  nothing (direct DB check); transient RDW failure still creates an
  unenriched retry row (unchanged behavior, re-asserted); `lookup_vehicle`
  returns `None` for a new not-found kenteken and persists nothing;
  `lookup_vehicle` keeps an already-known vehicle even when RDW later
  reports it missing.
- New tests in `test_tools.py` (RDW outage reported gracefully, not
  raised) and `test_vehicles_router.py` (404 on confirmed not-found).
- An existing test, `test_documents.py::test_upload_triggers_vehicle_
  detection_and_creates_entity`, asserted the *old* behavior (vehicle
  created even when RDW returns not-found) — updated to mock a found
  response instead, since that's what the test's name/intent actually
  needed (proving detection triggers entity creation). Left in the known
  pre-existing 14-item baseline failure set, unrelated to this change —
  see "Testing note" below.
- **Testing note**: a version of this fix that added a *second*
  `test_documents.py` test (asserting the not-found path via a full
  document upload) was reverted. That test path goes through the real
  async event pipeline (`EMBEDDINGS_CREATED` → `_handle_extract_vehicles`),
  which does not reliably complete before the test's immediate follow-up
  assertion in this environment — a pre-existing test-timing issue
  unrelated to this change. The direct-unit-test coverage in
  `test_vehicle_agent.py` (calling `detect_and_link_vehicles` directly,
  no event-pipeline dependency) is the reliable coverage for this
  feature; going through the upload pipeline for this specific assertion
  would have been flaky regardless of correctness.
- Full backend suite: 332 passed, 14 failed — exactly the known
  pre-existing baseline (`test_ai_gateway`, `test_chat` x2,
  `test_documents` x3, `test_entities` x7), zero new failures.
- Deployed live; verified via the same reload-log + health-check pattern
  as every prior phase.
