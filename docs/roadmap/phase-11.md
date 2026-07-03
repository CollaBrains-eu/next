# Phase 11 — Multi-Agent System

> **Status: done.** Built as: the model itself is the Manager (no
> separate Agent-descriptor abstraction), offered the calling user's
> permitted tools via 9d's native function-calling, dispatching at most
> one per request (ADR 0026). See `README.md` for the summary and ADR
> 0026 for what actually shipped vs. what this spec originally proposed
> (Planning Engine's fixed templates were kept, not replaced). Kept
> here as historical context for how the open design questions got
> resolved.

## Goal

Replace hardcoded agent dispatch (Phase 8c's `AGENT_DISPATCH` dict,
`planning_engine.py`'s fixed goal → step-sequence templates) with a
Manager Agent that chooses which agent handles a request at runtime,
based on each agent's declared capabilities — not a lookup table the
calling code owns.

## Why now

Phase 8c deliberately used fixed, deterministic step templates instead
of an LLM-improvised task graph (ADR 0019), for the same "smallest safe
slice" reason ADR 0004 scoped down the Legal Agent. That was the right
call for Phase 8c's scope. A Manager Agent is the next step up: it
still needs each candidate agent to expose the same kind of structured
description Phase 9's Tool Registry gives to tools, so the Manager can
reason about "which agent can do this" instead of a human encoding that
decision into a dict.

## Structure

Instead of:

```
Planner
  ↓
Legal
```

(one fixed hardcoded chain, decided by the calling code)

```
Manager Agent
  ↓
Planner
  ↓
Search
  ↓
Entity
  ↓
Legal
  ↓
Document
  ↓
Communication
  ↓
Reasoning
```

(Manager selects the path per-request)

Each agent declares:

- **Capabilities** — what kinds of requests it can handle (likely
  expressed via Phase 9's tool descriptors, so an agent's capability is
  "the set of tools it's allowed to call" rather than a separate
  description format).
- **Memory** — what context (Phase 8b memories, conversation history)
  it needs access to.
- **Allowed tools** — a permission-scoped subset of Phase 9's tool
  registry.
- **Cost** — a rough weight (LLM calls, latency) so the Manager can
  prefer a cheaper agent when multiple could handle a request.
- **Priority** — tie-breaking when multiple agents claim they can
  handle the same request.

The Manager picks the agent (or sequence); the agent's own code, not
the Manager, still decides how it executes once selected.

## Dependency on Phase 9

This phase assumes Phase 9's Tool Registry exists — an agent's
"capabilities" and "allowed tools" are only meaningfully structured data
once tools are self-describing rather than hardcoded imports. Sequencing
Phase 9 before Phase 11 is a hard dependency, not just a suggestion.

## Design questions to resolve before implementation

- Does the Manager itself call an LLM to choose an agent (risking the
  same non-determinism ADR 0019 avoided for plan steps), or is it a
  deterministic capability-matching function over declared agent
  metadata, with an LLM only used as a tie-breaker when multiple agents
  match equally well?
- What replaces `planning_engine.py`'s fixed goal templates — does the
  Planning Engine become a specific "Manager Agent policy" (goal →
  fixed steps, unchanged), while genuinely novel requests get routed
  through the new dynamic Manager? Likely yes: Phase 8c's deterministic
  templates don't need to be thrown away, just become one strategy the
  Manager can choose among.
- How does a failed agent selection surface — does the Manager retry
  with a different agent, same "retry-once-then-isolate" pattern as
  ADR 0019's plan step execution, or fail the request outright?

## Acceptance criteria

- At least two existing agents (e.g. Search and Legal) are re-expressed
  with declared capabilities/cost/priority, and the Manager correctly
  routes at least one real request to each based on those declarations,
  not a hardcoded if/else.
- Existing fixed-template Planning Engine goals (ADR 0019) keep working
  unchanged — this phase adds a new routing mechanism, it doesn't
  replace the one that already works.
