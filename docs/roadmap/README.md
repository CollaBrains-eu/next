# Roadmap: Phase 14 onward

Phases 0-13 are documented in the top-level `README.md` and their ADRs
(`docs/adr/0001` through `0028`). That README is now frozen as a
"what's done" overview — it does not grow a new paragraph per future
phase. Everything past Phase 13 lives here instead, one file per phase,
written before implementation starts so each phase is a self-contained
spec to build against (and, once built, gets its own ADR the same way
every phase so far has).

`phase-09.md` through `phase-13.md` are kept here as the historical
specs Phase 9 (ADRs 0021-0024), Phase 10 (ADR 0025), Phase 11 (ADR
0026), Phase 12 (ADR 0027), and Phase 13 (ADR 0028) were actually built
against -- useful context for how the design questions they raised got
resolved, even though all five phases are done.

## Why the roadmap changes shape here

Phases 0-8 were about giving the AI more things it could do: search,
draft, extract entities, remember, plan, reflect. Phase 8c (Planning
Engine) and 8d (Reflection Engine) are the first phases where the AI
started checking and sequencing its *own* work rather than just
answering a single request. Phase 9 (done) made the AI's capabilities
self-describing and discoverable; Phase 10 (done) gave it a real
knowledge graph beyond entities; Phase 11 (done) let the model itself
choose which tool to use for a free-form request; Phase 12 (done)
closed the "learn" gap in the observe/plan/execute/verify/learn cycle;
Phase 13 (done) gave it durable, explicit knowledge about a specific
user. Phase 14 onward keeps going:

- **9 — AI Platform** (done): tools become self-describing and
  discoverable instead of hardcoded into each agent.
- **10 — Knowledge Graph 2** (done): a `Decision` node type and a
  generalized graph-edge table.
- **11 — Multi-Agent System** (done): the model is the Manager,
  choosing which registered tool to call for a free-form request.
- **12 — Autonomous Workflows** (done): the "learn" step -- memories
  that contributed to a verified-sufficient answer get reinforced.
- **13 — Personal AI** (done): a durable `preferred_language`
  preference, changing `/chat` behavior without being restated.
- **14 — Enterprise**: organizations, teams, shared memory, governance,
  tenant isolation — the platform, not just the product. The highest
  blast-radius phase so far: a full multi-table `organization_id`
  retrofit against live production data is its own dedicated,
  carefully-staged undertaking, not something to do speculatively in
  one slice (see `phase-14.md`'s own design questions).
- **15 — Learning Platform**: a full feedback → evaluation → dataset →
  fine-tune → benchmark → deploy cycle, built *before* any custom model
  training, not instead of it.

## Phases

- ~~[Phase 9 — AI Platform](phase-09.md)~~ — done, see `README.md` and ADRs 0021-0024
- ~~[Phase 10 — Knowledge Graph 2](phase-10.md)~~ — done, see `README.md` and ADR 0025
- ~~[Phase 11 — Multi-Agent System](phase-11.md)~~ — done, see `README.md` and ADR 0026
- ~~[Phase 12 — Autonomous Workflows](phase-12.md)~~ — done, see `README.md` and ADR 0027
- ~~[Phase 13 — Personal AI](phase-13.md)~~ — done, see `README.md` and ADR 0028
- [Phase 14 — Enterprise](phase-14.md)
- [Phase 15 — Learning Platform](phase-15.md)

## Status

Phase 9 (ADRs 0021-0024), Phase 10 (ADR 0025), Phase 11 (ADR 0026),
Phase 12 (ADR 0027), and Phase 13 (ADR 0028) are done. Phase 14-15 are
vision documents only — none has started. Each still gets scoped down
to a "smallest safe slice" the way Phase 8's through 13's actual
implementations were before any code is written; these files describe
the target shape, not a locked implementation plan. Phase 14 in
particular will likely need multiple sub-phases given its migration
risk -- see `phase-14.md`.
