# Roadmap: Phase 9 onward

Phases 0-8 are documented in the top-level `README.md` and their ADRs
(`docs/adr/0001` through `0020`). That README is now frozen as a
"what's done" overview — it does not grow a new paragraph per future
phase. Everything past Phase 8 lives here instead, one file per phase,
written before implementation starts so each phase is a self-contained
spec to build against (and, once built, gets its own ADR the same way
every phase so far has).

## Why the roadmap changes shape here

Phases 0-8 were about giving the AI more things it could do: search,
draft, extract entities, remember, plan, reflect. Phase 8c (Planning
Engine) and 8d (Reflection Engine) are the first phases where the AI
started checking and sequencing its *own* work rather than just
answering a single request. Phase 9 onward continues that trajectory
instead of adding another isolated feature:

- **9 — AI Platform**: tools become self-describing and discoverable
  instead of hardcoded into each agent.
- **10 — Knowledge Graph 2**: the entity graph (Person/Document, one hop)
  becomes a real multi-type knowledge graph the AI can reason over.
- **11 — Multi-Agent System**: a Manager Agent chooses which agent
  handles a request, instead of the calling code deciding.
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

- [Phase 9 — AI Platform](phase-09.md)
- [Phase 10 — Knowledge Graph 2](phase-10.md)
- [Phase 11 — Multi-Agent System](phase-11.md)
- [Phase 12 — Autonomous Workflows](phase-12.md)
- [Phase 13 — Personal AI](phase-13.md)
- [Phase 14 — Enterprise](phase-14.md)
- [Phase 15 — Learning Platform](phase-15.md)

## Status

Vision documents only — none of Phase 9-15 has started. Each phase
still gets scoped down to a "smallest safe slice" the way Phase 8's four
sub-phases were (see ADR 0004's original framing, reapplied in ADRs
0017-0020) before any code is written; these files describe the target
shape, not a locked implementation plan.
