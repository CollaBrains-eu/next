# ADR 0020: Phase 8d — Reflection Engine

## Status
Accepted

## Context

The roadmap's Phase 8d asks for every generated answer to be automatically
reviewed for hallucination risk: "Reflection runs after planning. Missing
evidence triggers another retrieval. Hallucination risk reduced. Reflection
result stored in audit log."

The two places this matters most today are `/chat` (ADR 0003) and
`/legal/draft` (ADR 0004) — both are RAG endpoints that generate free text
grounded in retrieved context, and both are explicitly documented as
"say so instead of guessing" / "never fill gaps with assumptions." A
reflection step is a second, independent check on whether the model actually
honored that instruction, not a replacement for it.

The roadmap also names a Planning Engine (8c) as something reflection runs
"after." Plan steps (8c) dispatch to the same underlying agents (Document,
Legal, Entity) that already call through the AI Gateway — wiring reflection
into the two generation call sites it ultimately bottlenecks through is a
smaller, safer slice than adding a parallel reflection pass inside
`execute_plan` itself, and gets the same coverage: any plan step that ends up
drafting or summarizing text goes through `/legal/draft`'s or the same
underlying generation path that chat and drafting share. Given 8c is a
sibling unmerged branch, this phase is built independently against `main`,
same as 8a/8b/8c were against each other.

## Decision

**Add a `reflect()` step, run synchronously, right after generation, in both
`/chat` and `/legal/draft`.** It must run synchronously (not as a background
task like memory extraction in 8b) because its outcome — "the context was
insufficient" — needs to be able to change the answer that's actually
returned, not just get logged after the fact.

**Reflection is a second LLM call** (json-mode, grammar-constrained, same
pattern as the Entity Agent and Memory extraction), asked to judge, given the
question, the context excerpts, and the generated answer:
- `sufficient_evidence`: did the context contain enough to answer the
  question, and is every claim in the answer backed by it?
- `confidence`: 0-100.
- `issues`: short list of specific problems found, if any.

**On `sufficient_evidence: false`, retry once with a wider retrieval** (double
`context_chunks`, capped at 20) and regenerate. This mirrors the retry-once
pattern from ADR 0019's plan step execution — one bounded retry, then accept
the outcome, rather than looping. The retried answer is not re-reflected; the
roadmap's acceptance criterion is "missing evidence triggers another
retrieval," not an unbounded self-correction loop, and re-reflecting doubles
LLM cost for a check that's already served its purpose (widen context once).

**Reflection results are stored in a new `reflection_log` table**, not bolted
onto `ai_call_log`. `ai_call_log` (ADR 0003) is a record of raw model calls;
a reflection is a judgment *about* a previous call's output, a different kind
of fact. Keeping it separate avoids changing `chat_completion`'s signature
or its callers' existing mocks (`api.chat.chat_completion`,
`api.legal.chat_completion`) — a smaller, lower-risk change than threading a
log-row id back out of the AI Gateway.

**A reflection failure must never fail or change the primary response.** The
whole reflect-retry-log sequence is wrapped in one try/except per endpoint,
matching the established pattern (Signal notifications, auto-extraction,
event bus dispatch, 8b's memory retrieval/creation, 8c's plan step
execution). If the reflection LLM call fails, times out, or returns
unparseable JSON, the endpoint falls back to the originally generated answer
and skips logging — a broken reflection subsystem must not make chat or
drafting unavailable.

## Consequences

- Every `/chat` and `/legal/draft` call now costs one extra LLM round-trip
  (two if evidence is insufficient), which is a real latency/cost tradeoff
  accepted for the smallest safe slice. If this proves too slow in practice,
  a documented future option is to make reflection fire-and-forget
  (log-only, no retry) and only escalate to a blocking retry above some
  volume of user-reported hallucinations — deferred until there's a second
  real signal justifying it, same reasoning ADR 0004 applied to scoping the
  Legal Agent itself.
- `reflection_log` gives operators a queryable record of how often the
  system judges its own answers under-evidenced, per endpoint, without
  requiring a human to notice a bad answer first.
- Not wired into Planning Engine (8c) plan steps directly in this slice —
  `execute_plan`'s Document/Legal Agent dispatch calls the same
  `_generate_summary`/`_generate_draft` functions, but those don't go through
  the two HTTP endpoints reflection is attached to. Extending reflection to
  cover plan-step-initiated generation directly is deferred until 8c and 8d
  are both merged to `main` and can be composed safely.
