# ADR 0027: Phase 12 — Autonomous Workflows

## Status
Accepted

## Context

`docs/roadmap/phase-12.md` frames this phase as closing an
observe → plan → execute → verify → learn cycle, and is explicit that
four of the five steps already exist, individually, elsewhere in this
codebase:

- **Observe**: Phase 8a's event bus already runs the document pipeline
  (`DocumentUploaded` → `OCRCompleted` → `EmbeddingsCreated` →
  `TasksCreated`/`EntitiesExtracted` → `NotificationRequested` →
  `WorkflowCompleted`) unattended, no human triggering each step. This
  is already, today, "one real trigger runs a genuinely multi-step
  workflow end to end with no human intervention" -- the roadmap's own
  acceptance criterion for this phase is already met by existing code,
  not something this phase needs to build.
- **Plan**: Phase 8c's Planning Engine.
- **Execute**: the existing agents.
- **Verify**: Phase 8d's Reflection Engine.

The one genuinely missing piece, per the roadmap doc's own framing, is
**Learn** -- "the system adjusts its own future behavior based on
outcomes," explicitly distinct from Phase 15's model fine-tuning. This
ADR is that piece, and only that piece.

## Decision

**"Learn" means: a memory that demonstrably helped produce a
verified-sufficient answer gets its `importance` reinforced.** Of the
roadmap doc's three candidate mechanisms (reflection verdicts feeding
goal-template selection; memory importance feeding off usage; anything
resembling fine-tuning), this is the one with the least new
infrastructure and the most direct wiring between two systems that
already exist and already sit next to each other in the same request:
`/chat` already retrieves memories (Phase 8b) and already reflects on
whether the answer they contributed to was sufficient (Phase 8d, ADR
0020). Nothing about reflection-verdicts-choosing-goal-templates exists
yet to hook into (Planning Engine's goal selection is still explicit,
per-request, ADR 0019/0026), so that candidate isn't buildable as a
small slice today.

**Reward only, no decay.** `api/memory.py`'s new `reinforce_memories()`
bumps `importance` (capped at 100) for every memory that was offered to
the model *and* whose resulting answer Reflection judged
`sufficient_evidence: true`. There is no symmetric penalty when
`sufficient_evidence` is `false`: an insufficient-evidence verdict could
be about missing *document* context, not the memory's fault (`/chat`
offers memories and documents together in one prompt; reflection judges
the answer as a whole, not per-source). Decaying a memory's importance
based on a verdict that can't be attributed specifically to it would be
an unjustified inference the data doesn't support.

**Wired into `/chat` only, not a new "workflow" abstraction.** No new
`Workflow` model, no new state machine, no change to how `/chat`'s
existing reflection retry behaves. `reinforce_memories()` is called
once, inside the same try/except reflection already runs in
(`chat.py`), right after `log_reflection()` -- a memory-reinforcement
failure must never fail the chat response, the same "side effect never
fails the primary flow" pattern used everywhere else in this codebase.

**Everything else the roadmap names for this phase is out of scope
here, deliberately**, because it's either already done or not yet
buildable as a small slice:

- The example end-to-end workflow (letter → OCR → Entity → Planner →
  Legal → Summary → Signal → Calendar → Reminder) needs a calendar tool
  that doesn't exist (Phase 9a explicitly deferred calendar/mail
  integrations) and needs Legal drafting wired into the automatic
  pipeline, which would mean autonomously invoking an
  approval-gated goal (ADR 0019) -- a real runaway-automation risk the
  roadmap doc itself flags, not something to wire in without a
  concrete design for how automatic approval-gating gets preserved.
- Feeding Reflection verdicts into goal-template selection: no
  mechanism exists yet for goal templates to be "selected" rather than
  explicitly requested; premature to build a learning signal for a
  selection process that doesn't exist.

## Consequences

- A memory that keeps getting retrieved and keeps contributing to
  verified-good answers accumulates importance over time, all with
  code that already existed (Memory, Reflection) -- no new
  infrastructure, no new failure modes beyond one more DB write per
  chat request wrapped in the same try/except that already guards
  reflection.
- This phase does **not** demonstrate an autonomous workflow invoking
  an approval-gated Planning Engine goal, so the roadmap's "approval-
  gated goals remain gated inside an autonomous workflow" acceptance
  criterion isn't exercised here -- there's no new autonomous
  invocation path added that could violate it. Revisit when a future
  phase actually adds one.
- `importance`'s meaning shifts slightly: it was set once at creation
  (Phase 8b) by the extraction prompt's own judgment; it can now also
  grow afterward based on real usage outcomes. Both are still bounded
  0-100 (unchanged validation in `create_memory`).
