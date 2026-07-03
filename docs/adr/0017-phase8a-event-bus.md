# 0017: Phase 8a — Event Bus

## Status
Accepted (2026-07-03)

## Context
The Future Roadmap kicks off Phase 8 ("Cognitive Layer") with an event bus:
services publish and react to named events (`DocumentUploaded`,
`EmbeddingsCreated`, `TasksCreated`, ...) instead of calling each other
directly, with retry, a dead-letter queue, and structured event logging.
The stated goal is decoupling — "uploading a document no longer directly
invokes downstream services" — as the foundation for Phase 8b (memory),
8c (planning), and 8d (reflection), which all need to observe or trigger
off pipeline events rather than being wired into `documents.py` by hand.

Today the entire ingest pipeline is one function,
`api/documents.py::_process_document`, called via FastAPI's
`BackgroundTasks` from the upload endpoint. It does OCR, chunking,
embedding, task extraction, entity extraction, and Signal notification in
one sequential pass, with each optional step individually wrapped in
`try/except Exception: # noqa: BLE001 - must never fail the ingest
pipeline`. This is the same shape ADR 0004 chose for the workflow engine:
a real in-process trigger, not a queue/worker system, because there was
only one trigger source and no second consumer.

That condition has changed. Phase 3 (Signal) and Phase 4 (entities) both
now hang additional behavior off the same lifecycle transitions this
pipeline already produces, and Phase 8b–8d all need to subscribe to them
too. A real publish/subscribe seam is justified now in a way it wasn't at
ADR 0004.

## Decision

### In-process dispatch, durably logged — not a new deployable service yet
The roadmap names `services/events` as a "new service." Every other
`services/*` directory in this repo is a README stub until a phase
actually builds it out (see `pyproject.toml`'s workspace comment), and the
one existing "service" that isn't a stub, `services/api`, is a single
FastAPI monolith. Standing up `services/events` as its own deployable
process (new container, new broker role, new failure domain) has no
justification yet: every publisher and every subscriber for the initial
event set lives in the same process as `services/api`.

Instead, `api/events.py` adds an `EventBus` used in-process:

- `publish(event_type, payload)` awaits every subscriber registered for
  that type inline, in the same call, the same way `_process_document`
  already called `extract_tasks`/`extract_entities`/`send_signal_message`
  inline. This keeps timing identical to today — no new race between an
  HTTP response and a separate consumer loop — so the existing test suite
  (which asserts on document state immediately after `POST /documents`
  completes) needed no timing changes, only patch-target updates for
  handlers that moved modules.
- Every publish also durably appends the event to a Redis Stream
  (`collabrains:events:{type}`) via `XADD`, independent of whether any
  handler runs or succeeds. This is the real difference from a plain
  in-process callback list: there's an audit log, and it's what the DLQ
  and retry accounting are built on.
- A subscriber failure is retried inline with backoff (1s/5s/15s, 3
  attempts) before the event is written to `{stream}:dlq` and logged at
  ERROR. This replaces the per-call-site `# noqa: BLE001` try/excepts in
  `documents.py` with one centralized policy — a subscriber failing (e.g.
  entity extraction erroring) still can never fail the publisher, now
  enforced by the bus instead of by convention at each call site.
- Idempotency: each `Event` gets a UUID; the bus does a Redis
  `SET NX EX` per `(event_id, handler)` before invoking a handler, so a
  replayed or duplicate event (e.g. from manual DLQ replay tooling later)
  is a no-op rather than double-processing.

Because the durable log and retry/DLQ bookkeeping already go through
Redis Streams, splitting dispatch into a real cross-process consumer
group later (once Phase 8c's planner or a second service needs to consume
independently) is a change to `EventBus`'s internals, not to any
`publish()` call site. Revisit then, the same way ADR 0004 deferred
Celery until Signal gave the workflow engine a second trigger source.

### Initial events wired to the real pipeline, not stubbed
All nine initial events from the roadmap are defined in
`EventType`. `documents.py`'s upload endpoint now does nothing but persist
the `Document` row and publish `DocumentUploaded` — the OCR, embedding,
task/entity extraction, and notification steps are subscribers, each
publishing the next event in the chain (`OCRCompleted` →
`EmbeddingsCreated` → `TasksCreated` / `EntitiesExtracted` →
`NotificationRequested` → `WorkflowCompleted`). `SummaryCreated` is
published from the existing `/documents/{id}/summarize` endpoint when a
summary is actually (re)generated.

### What's out of scope for 8a
No new consumers beyond what already existed as direct calls — this
phase decouples the existing pipeline, it doesn't add new behavior. No
cross-process consumer group, no separate `events` container, no replay
CLI (the DLQ stream is inspectable directly via `redis-cli XRANGE`).
Those are real follow-ups once something other than `services/api` needs
to consume, per Phase 8b/8c.

## Consequences
- `documents.py` no longer imports `extract_tasks`, `extract_entities`, or
  `send_signal_message` for the ingest path directly; those calls happen
  inside event handlers in the same module, keeping the diff small.
- Tests that patched `api.documents.send_signal_message` to assert
  notification behavior are unaffected (the handler still lives in
  `documents.py`); tests asserting on document state after upload
  continue to work unchanged because dispatch is inline/awaited.
- A failed document (Paperless unreachable, etc.) still notifies the
  owner and still records `status="failed"` — that path publishes
  `NotificationRequested`/`WorkflowCompleted` with `outcome="failed"`
  instead of calling `_notify_owner` directly.
