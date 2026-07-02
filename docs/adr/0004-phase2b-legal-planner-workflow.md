# 0004: Phase 2b — Legal Agent, Planner Agent, Workflow Trigger

## Status
Accepted (2026-07-02)

## Context
Phase 2b is the remainder deferred from ADR 0003: Legal Agent, Planner
Agent, and the workflow engine. Each is scoped down to a concrete,
buildable, safe first slice rather than the full ambition implied by the
stub READMEs — consistent with how Phase 1 and 2a were scoped.

## Decisions

### Legal Agent: grounded drafting, not free-form legal advice
`POST /legal/draft` takes a drafting instruction (e.g. "draft an objection
to the request for extension") and optional document IDs to scope context.
It retrieves relevant chunks via the Search Agent (same as `/chat`),
builds a draft strictly from that retrieved context via the AI Gateway,
and returns the draft plus citations plus a fixed disclaimer.

This is deliberately NOT a general legal-reasoning chatbot. A 3B local
model has no reliable knowledge of case law or statutes, and inventing
citations would be actively harmful in a legal context (unauthorized
practice of law risk, professional liability for anyone relying on it).
The system prompt explicitly forbids citing anything not present in the
retrieved context, and every response is framed as a draft requiring
attorney review, never as advice or a final filing. If a request can't be
grounded in ingested documents (no matching context), the agent says so
rather than drafting from the model's general knowledge.

### Planner Agent: task extraction, not scheduling
`POST /documents/{id}/extract-tasks` asks the LLM to extract actionable
items (title, description, due date if mentioned, assignee if mentioned)
from a single document's OCR text as structured JSON, and persists them
as rows in a new `tasks` table. `GET /tasks` lists them.

No calendar integration, no recurring events, no notification/reminder
system, no assignment-to-real-users (assignee is free text) — those are
separate features with their own design needs. This is deliberately the
smallest useful slice: turn unstructured document text into a checkable
list of things someone needs to do.

### Workflow engine: an in-process trigger, not Celery yet
The workflow stub README specifies "Celery-based, Signal-triggerable."
Neither half of that is warranted yet: Signal isn't built (Phase 3, no
phone number provisioned), so there's nothing to trigger *from* besides
the document pipeline itself, and the existing in-process asyncio
background-task pattern (ADR 0002's reasoning for skipping a task queue at
current scale) still holds -- introducing Celery now means a new worker
process, a new broker role for Redis, and new deployment/failure-mode
surface area for a single trigger with no external caller yet.

Instead: when a document's background processing reaches `status="ready"`
(`api/documents.py::_process_document`), it optionally calls the Planner
Agent's extraction function directly, in-process, gated by
`settings.auto_extract_tasks_on_ready` (default on). This is a real,
working "event → trigger → agent" mechanism -- the actual shape a
workflow engine needs -- without a BPMN-style rules DSL or new
infrastructure that has no second consumer yet. Revisit with Celery once
Signal (Phase 3) gives the workflow engine an actual second trigger source
and the durability/retry guarantees Celery provides become worth their
operational cost.

### Schema
`tasks` (id, document_id nullable FK, title, description, due_date
nullable, assignee nullable free text, status [open|done], source
[manual|planner_agent], created_by nullable FK to users, created_at).
