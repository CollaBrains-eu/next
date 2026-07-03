# ADR 0030: Phase 15 — Learning Platform (dataset export only)

## Status
Accepted

## Context

`docs/roadmap/phase-15.md` proposes a full pipeline: Feedback →
Evaluation → Synthetic Data → Dataset → Fine Tune → Benchmark → Deploy.
Its acceptance criteria are (1) a dataset producible from real
Reflection Engine and approval signal end to end, without manual
collection, and (2) a fine-tuned model only deployed after beating the
base model on a benchmark set, enforced by the pipeline.

This is the last phase of the original roadmap, and by far the
riskiest to actually build in full. The roadmap's own design questions
already flag why: "the production host is CPU-only and already the
bottleneck at 8 concurrent chat users" (ADR 0015's load test). Real
fine-tuning needs a training framework this environment has none of,
meaningful GPU/CPU budget this host doesn't have spare, and a benchmark
methodology that doesn't exist yet either. Building `Fine Tune`,
`Benchmark`, or `Deploy` here would mean either faking them (a
placeholder that doesn't actually improve anything) or genuinely
running a training job that could degrade this production host for
real users -- neither is acceptable.

## Decision

**This phase delivers Feedback → Evaluation → Dataset only.**
`Synthetic Data`, `Fine Tune`, `Benchmark`, and `Deploy` are not built
-- not stubbed, not scaffolded, simply not present, per this project's
standing rule against half-finished implementations. The roadmap's
first acceptance criterion (a dataset, producible end to end from real
signal) is delivered honestly; the second (benchmark-gated deployment)
is not attempted, because attempting it without real training
infrastructure would mean faking the one guarantee that makes a
learning platform trustworthy at all.

**Two real signal sources, no synthetic data.** `docs/roadmap/phase-15.md`
names Reflection verdicts (8d) and approval/rejection decisions (8c) as
real feedback that already exists -- this phase exports exactly those,
nothing invented:

- **Plan approval examples**: every completed `legal_agent` `PlanStep`
  already stores its actual input (`input_data["instruction"]`) and
  output (`result_data["draft"]`) -- a genuine input/output pair, not
  something added for this phase. Labeled `approved` if the parent
  `Plan.approved_at` is set (a human explicitly signed off on this
  draft leaving the system, ADR 0019/0025) or `unapproved` otherwise.
  This is the closest thing this codebase has to a supervised
  fine-tuning example today.
- **Reflection examples**: every `ReflectionLog` row (question,
  `sufficient_evidence`, `confidence`, `issues`) -- a genuine quality
  signal, though notably *not* an input/output pair, since
  `ReflectionLog` never stored the answer text itself (ADR 0020 logged
  only the verdict, not a transcript). Still directly useful as
  Evaluation data: which kinds of questions the system judges its own
  answers insufficient for.

**No `Synthetic Data` stage**: augmenting real feedback with generated
variations needs a real dataset to have first proven the signal is
worth augmenting, and needs a place to store/version synthetic examples
distinctly from real ones -- premature before either exists.

**`GET /learning/dataset`, admin-only.** Exports both signal sources as
one versioned JSON payload (`generated_at` timestamp, both example
lists). Admin-only because this is inherently an export of real user
questions and drafted document content, the most sensitive data surface
any endpoint in this codebase has touched -- narrower access than any
prior phase's default.

## Consequences

- **The roadmap's second acceptance criterion (benchmark-gated
  fine-tuned model deployment) is not met, deliberately, and should not
  be treated as a small remaining gap.** It requires: a training
  framework, compute this host doesn't have spare (ADR 0015), a defined
  benchmark set, and a rollback plan -- all real infrastructure
  decisions, not a coding task this session can responsibly close out.
  This is the most honest way to end a 15-phase roadmap: the last
  stages are named, understood, and explicitly not faked.
- The `legal_agent` approval-example source only covers
  `draft_legal_document`/`prepare_objection` goals -- other goal types'
  `PlanStep.result_data` don't carry comparable free-text output today.
  Extending example extraction to more goal types is real future work,
  not needed to prove the export mechanism works.
- No data is deleted, anonymized, or specially retained for this
  export beyond what `PlanStep`/`ReflectionLog` already keep under
  their own existing lifecycle -- this phase only reads, it doesn't
  introduce new retention obligations.
