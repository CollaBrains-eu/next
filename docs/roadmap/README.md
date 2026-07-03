# Roadmap: Phase 15 onward

Phases 0-14 are documented in the top-level `README.md` and their ADRs
(`docs/adr/0001` through `0029`). That README is now frozen as a
"what's done" overview — it does not grow a new paragraph per future
phase. Everything past Phase 14 lives here instead, one file per phase,
written before implementation starts so each phase is a self-contained
spec to build against (and, once built, gets its own ADR the same way
every phase so far has).

`phase-09.md` through `phase-14.md` are kept here as the historical
specs Phase 9 (ADRs 0021-0024) through Phase 14 (ADR 0029) were
actually built against -- useful context for how the design questions
they raised got resolved, even though all six phases are done.

**Phase 14 is only a foundation slice**, not the roadmap's full
Enterprise vision -- see `phase-14.md`'s status note and ADR 0029 for
exactly what's still missing (per-table tenant isolation, Teams, shared
memory, AI governance, RBAC 2.0) before treating "Enterprise" as
finished.

## Why the roadmap changes shape here

Phases 0-8 were about giving the AI more things it could do: search,
draft, extract entities, remember, plan, reflect. Phase 8c (Planning
Engine) and 8d (Reflection Engine) are the first phases where the AI
started checking and sequencing its *own* work rather than just
answering a single request. Phases 9-13 (all done) made the AI's
capabilities discoverable, gave it a knowledge graph, let it choose its
own tools, closed the "learn" loop, and gave it durable per-user
knowledge. Phase 14 (foundation done) started -- but did not finish --
turning the platform into a multi-tenant product. Phase 15 onward:

- **9 — AI Platform** (done)
- **10 — Knowledge Graph 2** (done)
- **11 — Multi-Agent System** (done)
- **12 — Autonomous Workflows** (done)
- **13 — Personal AI** (done)
- **14 — Enterprise** (foundation done; full tenant isolation, Teams,
  RBAC 2.0 still open -- see ADR 0029)
- **15 — Learning Platform**: a full feedback → evaluation → dataset →
  fine-tune → benchmark → deploy cycle, built *before* any custom model
  training, not instead of it.

## Phases

- ~~[Phase 9 — AI Platform](phase-09.md)~~ — done, see `README.md` and ADRs 0021-0024
- ~~[Phase 10 — Knowledge Graph 2](phase-10.md)~~ — done, see `README.md` and ADR 0025
- ~~[Phase 11 — Multi-Agent System](phase-11.md)~~ — done, see `README.md` and ADR 0026
- ~~[Phase 12 — Autonomous Workflows](phase-12.md)~~ — done, see `README.md` and ADR 0027
- ~~[Phase 13 — Personal AI](phase-13.md)~~ — done, see `README.md` and ADR 0028
- [Phase 14 — Enterprise](phase-14.md) — foundation done, full scope still open, see ADR 0029
- [Phase 15 — Learning Platform](phase-15.md)

## Status

Phase 9 (ADRs 0021-0024), Phase 10 (ADR 0025), Phase 11 (ADR 0026),
Phase 12 (ADR 0027), and Phase 13 (ADR 0028) are done. Phase 14 is a
foundation slice (ADR 0029) with real, named remaining work (per-table
tenant isolation and its adversarial test, Teams, RBAC 2.0). Phase 15
is a vision document only -- not started. Each phase gets scoped down
to a "smallest safe slice" before any code is written; these files
describe the target shape, not a locked implementation plan.
