# Roadmap: all phases done, this is now historical reference

**All 15 phases of the original roadmap are done.** This directory's
files (`phase-09.md` through `phase-15.md`) are kept as the historical
specs each phase was actually built against -- useful context for how
the design questions they raised got resolved, not a queue of
remaining work. `README.md` at the repo root is the authoritative
"what's done" record and is now frozen; ADRs `0001` through `0030`
cover every design decision behind it.

**Two phases were deliberately scoped down and stay open on purpose**
-- read their status notes and ADRs before assuming either is
"finished" in the sense the original spec described:

- **Phase 14 (Enterprise)** -- foundation only. `Organization` and one
  policy override exist; per-table tenant isolation, Teams, shared
  memory, AI governance, and RBAC 2.0 do not (ADR 0029). The
  adversarial cross-org isolation test the original spec's acceptance
  criteria demanded was never attempted -- the migration risk of
  touching every existing table at once was judged too large for one
  slice, on a live production system with real user data.
- **Phase 15 (Learning Platform)** -- dataset export only. Feedback,
  Evaluation, and Dataset are built from real Reflection/approval
  signal; Synthetic Data, Fine Tune, Benchmark, and Deploy are not,
  because this environment has no training framework and the
  production host is already CPU-bound at low concurrency (ADR 0015).

## If there's a Phase 16

There's no Phase 16 spec yet -- none is needed until there's a concrete
next goal. When one exists, the discipline that got Phases 9-15 built
should carry forward: write the spec here first (goal, why now, open
design questions, acceptance criteria), scope it down to a smallest
safe slice before writing code, and give it its own ADR once built.
The two open threads above (finishing Phase 14's tenant isolation, or
picking Phase 15 back up once real training infrastructure exists) are
the most obvious starting points, but neither is a foregone conclusion
-- a genuinely new goal is just as valid a Phase 16.

## Phases (all done, historical)

- [Phase 9 — AI Platform](phase-09.md) — ADRs 0021-0024
- [Phase 10 — Knowledge Graph 2](phase-10.md) — ADR 0025
- [Phase 11 — Multi-Agent System](phase-11.md) — ADR 0026
- [Phase 12 — Autonomous Workflows](phase-12.md) — ADR 0027
- [Phase 13 — Personal AI](phase-13.md) — ADR 0028
- [Phase 14 — Enterprise](phase-14.md) — foundation only, ADR 0029
- [Phase 15 — Learning Platform](phase-15.md) — dataset export only, ADR 0030
