# Phase 12 — Autonomous Workflows

## Goal

Close the loop from "the AI executes a task when asked" to a full
**observe → plan → execute → verify → learn** cycle that runs without a
human triggering each step — Phase 8a's event bus provides the
"observe" trigger, 8c the "plan"/"execute", 8d the "verify"; this phase
adds "learn" and chains all five into workflows that run end to end
unattended.

## Why now

The pieces already exist individually:

- **Observe**: Phase 8a's event bus (`DocumentUploaded`,
  `EmbeddingsCreated`, etc.)
- **Plan**: Phase 8c's Planning Engine
- **Execute**: existing agents (Document, Legal, Entity, Planner)
- **Verify**: Phase 8d's Reflection Engine

What's missing is (a) a "learn" step that feeds outcomes back in, and
(b) wiring these into one continuous chain per real-world trigger,
instead of each phase's capability being invoked independently via its
own endpoint.

## Example end-to-end workflow

```
New letter arrives
  ↓
OCR
  ↓
Entity extraction
  ↓
Planner (task extraction)
  ↓
Legal (draft response, if warranted)
  ↓
Summary
  ↓
Signal notification
  ↓
Calendar check (does this conflict with an existing deadline?)
  ↓
Reminder scheduled
```

All automatic — the human sees the outcome (a Signal message, a
scheduled reminder), not each intermediate step.

## Design questions to resolve before implementation

- **What decides a workflow is complete/failed?** Phase 8c's
  `Plan.status` (`completed`/`partially_failed`/`failed`) is the
  existing model for this — does an autonomous workflow reuse `Plan`
  directly, or is a workflow a different concept that *contains*
  one or more plans?
- **What does "learn" mean concretely?** Candidates, roughly in order
  of how directly they build on existing phases: (a) feeding Reflection
  Engine (8d) verdicts back into which goal templates get chosen for
  similar future triggers; (b) adjusting Phase 8b memory importance
  scores based on whether a memory actually got used and was useful;
  (c) anything resembling model fine-tuning is explicitly Phase 15's
  scope, not this phase's — "learn" here means the system adjusts its
  own future behavior, not that a model gets retrained.
- **Calendar/mail integration**: the example workflow needs a calendar
  tool that doesn't exist yet. This is a dependency on Phase 9's Tool
  Registry providing a place for that integration to live, not
  something this phase should build ad hoc.
- **Runaway automation risk**: Phase 8c already gates goals whose
  output leaves the system (drafts) behind explicit approval. An
  autonomous workflow chaining multiple such goals needs the same
  gating to survive intact — this phase must not quietly bypass ADR
  0019's approval requirement by wrapping a gated goal inside an
  ungated workflow.

## Acceptance criteria

- One real trigger (e.g. document upload) runs a genuinely multi-step
  workflow end to end with no human intervention between steps, and
  produces a verifiable outcome (a sent Signal message, a created
  Task) — not just a chain of function calls that individually "could"
  compose.
- Approval-gated goals (ADR 0019) remain gated when invoked from inside
  an autonomous workflow — verified with a test, not just by
  inspection.
