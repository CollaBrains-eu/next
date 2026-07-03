# Roadmap: Phase 11 onward

Phases 0-10 are documented in the top-level `README.md` and their ADRs
(`docs/adr/0001` through `0025`). That README is now frozen as a
"what's done" overview — it does not grow a new paragraph per future
phase. Everything past Phase 10 lives here instead, one file per phase,
written before implementation starts so each phase is a self-contained
spec to build against (and, once built, gets its own ADR the same way
every phase so far has).

`phase-09.md` and `phase-10.md` are kept here as the historical specs
Phase 9 (ADRs 0021-0024) and Phase 10 (ADR 0025) were actually built
against -- useful context for how the design questions they raised got
resolved, even though both phases are done.

## Why the roadmap changes shape here

Phases 0-8 were about giving the AI more things it could do: search,
draft, extract entities, remember, plan, reflect. Phase 8c (Planning
Engine) and 8d (Reflection Engine) are the first phases where the AI
started checking and sequencing its *own* work rather than just
answering a single request. Phase 9 (done) made the AI's capabilities
self-describing and discoverable; Phase 10 (done) gave it a real,
if still narrow, knowledge graph beyond entities. Phase 11 onward keeps
going:

- **9 — AI Platform** (done): tools become self-describing and
  discoverable instead of hardcoded into each agent.
- **10 — Knowledge Graph 2** (done): a `Decision` node type and a
  generalized graph-edge table -- scoped to one new node/relationship,
  not all ten the original spec proposed (see ADR 0025).
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
- ~~[Phase 10 — Knowledge Graph 2](phase-10.md)~~ — done, see `README.md` and ADR 0025
- [Phase 11 — Multi-Agent System](phase-11.md)
- [Phase 12 — Autonomous Workflows](phase-12.md)
- [Phase 13 — Personal AI](phase-13.md)
- [Phase 14 — Enterprise](phase-14.md)
- [Phase 15 — Learning Platform](phase-15.md)

## Status

Phase 9 (ADRs 0021-0024) and Phase 10 (ADR 0025) are done. Phase 11-15
are vision documents only — none has started. Each still gets scoped
down to a "smallest safe slice" the way Phase 8's, 9's, and 10's actual
implementations were before any code is written; these files describe
the target shape, not a locked implementation plan.
