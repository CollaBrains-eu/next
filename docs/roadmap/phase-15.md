# Phase 15 — Learning Platform

## Goal

Build a complete **feedback → evaluation → synthetic data → dataset →
fine-tune → benchmark → deploy** pipeline. This is the answer to the
original "can I build my own AI model?" question this project started
from — but the answer is "build the learning cycle first," not "start
fine-tuning now."

## Why last, and why a full cycle instead of "just fine-tune"

Fine-tuning without the surrounding cycle produces a model nobody can
evaluate, iterate on, or trust more than the general-purpose model it
replaced. Every phase before this one (8b memory, 8d reflection, 14
governance) produces exactly the kind of labeled signal a real learning
pipeline needs — reflection verdicts, memory usefulness, approval/
rejection decisions — so sequencing this phase last means the fine-
tuning data is a byproduct of a system that already exists, not
something collected from scratch for this purpose alone.

## Pipeline stages

```
Feedback
  ↓
Evaluation
  ↓
Synthetic Data
  ↓
Dataset
  ↓
Fine Tune
  ↓
Benchmark
  ↓
Deploy
```

- **Feedback** — real signal already produced by earlier phases:
  Reflection Engine verdicts (8d), approval/rejection decisions (8c),
  explicit user corrections (if a thumbs-up/down or edit-the-draft
  affordance exists in the frontend by this point).
- **Evaluation** — turning raw feedback into a scored dataset: which
  responses were flagged insufficient, which drafts got approved
  unedited vs. heavily rewritten.
- **Synthetic Data** — augmenting real feedback with generated
  variations, where real data is too sparse for a given task/domain to
  fine-tune on directly.
- **Dataset** — a versioned, reviewable training set — not just a
  database query re-run at fine-tune time; a fine-tune run needs to
  be reproducible against the exact dataset it was trained on.
- **Fine Tune** — actual model training, against the currently
  configured base model (`qwen2.5:3b-instruct` per ADR 0003, or
  whatever the current default is by the time this phase starts).
- **Benchmark** — the fine-tuned model must beat the base model on a
  held-out eval set before it's eligible for deploy — this is the gate
  that makes the rest of the pipeline meaningful; without it, "we fine-
  tuned a model" is not the same claim as "we made the model better."
- **Deploy** — swapping the model `AI Gateway` (ADR 0003) points at,
  presumably behind the same kind of gate Phase 14's governance
  policies would apply to any other AI-affecting change.

## Design questions to resolve before implementation

- **Where does compute for fine-tuning happen?** The production host
  is CPU-only and already the bottleneck at 8 concurrent chat users
  (ADR 0015/Phase 6d's load test) — fine-tuning cannot run on the same
  host as production inference without a real plan for isolating it
  (a separate host, off-peak scheduling, or an external fine-tuning
  service).
- **What's the benchmark set?** Needs to be defined before the first
  fine-tune run, not chosen after, to avoid picking an eval set that
  flatters whatever model happened to get trained.
- **Rollback**: if a deployed fine-tuned model performs worse in
  production than the benchmark predicted, what's the path back to the
  base model? This needs to be at least as fast as any other Phase 14
  governance rollback, not a special case.

## Acceptance criteria

- A dataset can be produced from real Reflection Engine (8d) and
  approval (8c) signal, end to end, without manual data collection.
- A fine-tuned model is only deployed after beating the base model on
  the benchmark set — enforced by the pipeline, not by a human
  remembering to check.
