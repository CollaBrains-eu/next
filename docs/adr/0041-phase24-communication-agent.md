# ADR 0041: Phase 24 — Communication Agent

## Status

Accepted

## Context

`docs/superpowers/plans/2026-07-09-fase1-admin-dashboard.md` §3.3
identified Communication Agent as the one missing link in the
Trigger -> Planner -> Legal -> Document -> Communication -> Notification
chain the original spec described. Every other step already dispatches
through the Planning Engine (ADR 0019); `agents/communication-agent/`
was a README-only stub with no implementation.

## Decision

**Grounded the same way Legal Agent is (ADR 0004), without Reflection
(ADR 0020).** `communication_agent.py::draft_communication` retrieves
context via `hybrid_search` and drafts only from what it finds, same
discipline as `legal.py`. Does not run a Reflection pass afterward --
Reflection exists for claims a reader could act on as unverified fact; a
communication draft is reviewed by its human sender before it's actually
sent regardless, so the extra LLM call isn't proportionate here the way
it is for a legal filing or a research answer.

**Registered as both a Planning Engine goal type and an `AGENT_DISPATCH`
entry**, not just the latter -- a new `draft_communication` goal type
(not approval-gated, unlike `draft_legal_document`/`prepare_objection`)
lets it be invoked the same way every other agent is, through
`POST /plans`, not as a special case.

## Consequences

- No new database tables or migrations -- this phase is pure agent
  logic, reusing `hybrid_search` and `chat_completion` unchanged.
- Verified end-to-end against the live stack: `POST /plans` with
  `goal_type=draft_communication` executed a real (not mocked) Ollama
  call and returned a coherent, structured draft in ~38s.
- Full test suite re-run after this change showed the identical 14
  pre-existing failures as before Phase 22/23, confirming no new
  regressions.

**Deploy-process bug caught and fixed during this phase's own rollout,
not by a review:** the rsync-based deploy step (used for Phase 22/23/24,
since this project has no CI/CD pipeline) synced this phase's branch
before re-fetching `origin/main` locally, so the branch was accidentally
built on top of Phase 22 only, missing Phase 23. Deploying it briefly
overwrote Phase 23's changes to `models.py`/`documents.py`/`events.py`/`config.py`
on the live checkout (working tree only, nothing was committed or
pushed) -- silently disabling document classification for a few minutes
with no errors or downtime. Caught immediately by grep-checking for
Phase 23's markers right after the Phase 24 deploy, fixed via
`git checkout --` to restore the committed versions, then a full test
run against the live checkout confirmed correctness. Lesson for any
future rsync-to-live-checkout deploy on this host: always `git fetch
origin main` immediately before branching for a new phase, not just
once at the start of a session -- a branch silently going stale between
phases is a real, live-production risk, not just a local inconvenience.
