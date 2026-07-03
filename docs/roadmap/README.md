# Roadmap: Phase 10 onward

Phases 0-9 are documented in the top-level `README.md` and their ADRs
(`docs/adr/0001` through `0024`). That README is now frozen as a
"what's done" overview — it does not grow a new paragraph per future
phase. Everything past Phase 9 lives here instead, one file per phase,
written before implementation starts so each phase is a self-contained
spec to build against (and, once built, gets its own ADR the same way
every phase so far has).

`phase-09.md` is kept here as the historical spec Phase 9 was actually
built against (ADRs 0021-0024) -- useful context for how the design
questions it raised got resolved, even though Phase 9 itself is done.

## Why the roadmap changes shape here

Phases 0-8 were about giving the AI more things it could do: search,
draft, extract entities, remember, plan, reflect. Phase 8c (Planning
Engine) and 8d (Reflection Engine) are the first phases where the AI
started checking and sequencing its *own* work rather than just
answering a single request. Phase 9 (done) continued that trajectory by
making the AI's capabilities self-describing and discoverable instead
of hardcoded. Phase 10 onward keeps going:

- **9 — AI Platform** (done): tools become self-describing and
  discoverable instead of hardcoded into each agent.
- **10 — Knowledge Graph 2**: the entity graph (Person/Document, one hop)
  becomes a real multi-type knowledge graph the AI can reason over.
- **11 — Multi-Agent System**: a Manager Agent chooses which agent
  handles a request, instead of the calling code deciding. Depends on
  Phase 9's Tool Registry existing (it does now).
- **12 — Autonomous Workflows**: observe → plan → execute → verify →
  learn loops that run without a human triggering each step.
- **13 — Personal AI**: the AI carries context about a specific user
  across sessions (preferences, style, active cases), not just
  per-conversation memory.
- **14 — Enterprise**: organizations, teams, shared memory, governance,
  tenant isolation — the platform, not just the product.
- **15 — Learning Platform**: a full feedback → evaluation → dataset →
  fine-tune → benchmark → deploy cycle, built *before* any custom model
  training, not instead of it.

## Phases

- ~~[Phase 9 — AI Platform](phase-09.md)~~ — done, see `README.md` and ADRs 0021-0024
- [Phase 10 — Knowledge Graph 2](phase-10.md)
- [Phase 11 — Multi-Agent System](phase-11.md)
- [Phase 12 — Autonomous Workflows](phase-12.md)
- [Phase 13 — Personal AI](phase-13.md)
- [Phase 14 — Enterprise](phase-14.md)
- [Phase 15 — Learning Platform](phase-15.md)

## Status

Phase 9 is done (ADRs 0021-0024). Phase 10-15 are vision documents only
— none has started. Each still gets scoped down to a "smallest safe
slice" the way Phase 8's and 9's sub-phases were before any code is
written; these files describe the target shape, not a locked
implementation plan.
