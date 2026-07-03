# 0019: Phase 8c — Planning Engine

## Status
Accepted (2026-07-03)

## Context
Everything built so far answers one request at a time: a chat question, a
document upload, a manual extraction call, a legal draft. The roadmap's
Phase 8c asks for a planner that turns a *goal* ("Summarise case", "Draft
legal document", "Prepare objection", "Analyse new upload", "Organise
document collection", "Generate timeline") into a task tree, executes it
against the existing agents, recovers from partial failures, and gates
anything with an external-facing output behind explicit approval.

## Decision

### Fixed goal templates, not an LLM-improvised task graph
`api/planning_engine.py` decomposes each of the six goals into a
**fixed, deterministic** step template parameterized by `goal_params`
(mostly `document_ids`) -- it does not ask an LLM to invent the plan
structure itself. This is the same call ADR 0004 made for the Legal
Agent: "grounded drafting, not free-form legal advice," because a small
local model has no reliable judgment for that and inventing structure
would be actively harmful. The risk here is the same shape one level up
-- a hallucinated or malformed *step graph* (wrong agent, missing step,
an infinite or cyclic plan) is a bigger and harder-to-audit failure mode
than a hallucinated sentence, and none of the six named goals actually
need dynamic structure: each is a short, well-known sequence of calls
into agents that already exist (Document Agent's summarizer, the
Planner/Entity Agents' extraction, the Legal Agent's draft, plus two new
deterministic aggregations -- see below). A "goal" is a lookup key into a
template, not a prompt handed to a meta-planner.

### The six goals, mapped onto existing agents
- **Analyse new upload** -> summarize (Document Agent) then extract tasks
  (Planner Agent) then extract entities (Entity Agent) for one document.
  This is the exact same pipeline the ingest flow already runs
  automatically when `auto_extract_tasks_on_ready`/`auto_extract_entities_on_ready`
  are enabled (ADR 0004) -- the Planning Engine just gives a caller a
  the same 3 steps re-run and inspect on demand, e.g. after a manual
  re-OCR or a document originally uploaded with auto-extraction disabled.
- **Summarise case** -> one Document Agent step per document in
  `goal_params.document_ids`. There's no `Case` model in the schema yet,
  so "case" here means exactly the document set the caller passes --
  scoping by an explicit ID list, the same choice `hybrid_search` and
  `/legal/draft` already made for `document_ids`.
- **Draft legal document** / **Prepare objection** -> one Legal Agent
  step. "Prepare objection" is the same drafting call with a canned
  instruction prefix ("Draft an objection...") plus caller-supplied
  grounds -- not a distinct agent, just a friendlier entry point to the
  same grounded-drafting call.
- **Organise document collection** -> a new deterministic aggregation
  (`organize_document_collection`): fetch the given documents plus every
  entity mentioned across them, grouped by type. No LLM call -- this is a
  database query, not a generative task, so there's nothing to hallucinate
  and no reason to spend a model call on it.
- **Generate timeline** -> a new deterministic aggregation
  (`generate_timeline`): every document's upload date plus every
  extracted task's due date across the given documents, sorted
  chronologically. Also a pure DB aggregation, not generative.

### Schema: `plans` + `plan_steps`
`Plan` (id, user_id, goal_type, goal_params JSONB, status, requires_approval,
created_at, approved_at, completed_at) and `PlanStep` (id, plan_id,
step_index, agent, input_data JSONB, status, result_data JSONB, error,
started_at, completed_at) -- a plan is its own row, steps are child rows
in a fixed order (`step_index`), not a generic graph/DAG structure, since
every current template is a straight sequence. Revisit if a future goal
needs branching or parallel steps.

### Approval gate: only the two goals with an externally-consumed output
`requires_approval` is true only for `draft_legal_document` and
`prepare_objection`. Those two produce content whose entire purpose is to
leave the system (a filing/objection draft for a human to review and use
externally) -- matching ADR 0004's framing that a legal draft is "always
a draft for attorney review, never a final filing." The Planning Engine
adds a real gate *before generation even runs*: `POST /plans` creates the
plan and its step(s) but does not execute anything for these two goal
types; only `POST /plans/{id}/approve` (owner or admin) triggers the LLM
call. This is a stricter posture than calling `/legal/draft` directly
today (which still runs immediately, no gate) -- deliberately so, since a
plan can be approved with less specific attention than crafting a direct
drafting request, so the Planning Engine adds the friction the direct
endpoint doesn't need to.

The other four goals are read/analysis-oriented and already run
unsupervised in other parts of the system (auto-extraction on upload,
`/documents/{id}/summarize` requires no approval today either) -- gating
them here would be inconsistent with established behavior for no added
safety, so they execute immediately via `BackgroundTasks` on `POST /plans`
(the same non-blocking mechanism the document upload endpoint uses),
leaving the plan/step rows for the caller to poll via `GET /plans/{id}`.

### Failure recovery: retry once, then isolate -- don't abort the plan
`execute_plan` runs steps in `step_index` order. A step that raises is
retried once immediately; if it still fails, that step is marked `failed`
with its error recorded, and **execution continues to the next step**
rather than aborting the whole plan. The plan's final status is
`completed` (all steps done), `failed` (all steps failed), or
`partially_failed` (a mix) -- so, e.g., in "summarise case" over five
documents, one OCR-less document failing to summarize doesn't block the
other four. This mirrors the "a side effect must never abort the whole
pipeline" rule already used for Signal notifications and auto-extraction
(ADR 0004, ADR 0007) -- applied here at the step-isolation level instead
of a single try/except per side effect.

### Independent of the (still-unmerged) Phase 8a/8b branches
Same reasoning as ADR 0018: the roadmap frames 8a-8d as "independently
deployable milestones." This phase calls the Planner/Entity/Document/Legal
Agents directly, the same way the pre-8a code did, rather than through
the Phase 8a event bus or Phase 8b's memory. Once those merge, publishing
`WorkflowStarted`/`WorkflowCompleted` around plan execution and letting
the memory extraction agent see plan outcomes are natural follow-ups, not
prerequisites.

## Consequences
- Extracted `_generate_summary` (from `documents.py`) and `_generate_draft`
  (from `legal.py`) into plain functions the HTTP endpoints and the
  Planning Engine both call, so there is exactly one implementation of
  each agent behavior. Endpoint behavior and existing tests are
  unaffected -- the extraction is a pure refactor, not a behavior change.
- No plan currently branches or runs steps in parallel; `step_index` is a
  strict linear order. A goal needing real parallelism or conditional
  branching is a schema change, not just a new template entry.
