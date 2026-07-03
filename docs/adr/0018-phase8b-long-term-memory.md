# 0018: Phase 8b — Long-term Memory

## Status
Accepted (2026-07-03)

## Context
Chat today (`api/chat.py`, ADR 0003) is stateless server-side: "no server-side
conversation memory yet either — callers pass prior turns themselves if they
want multi-turn context." Every answer is grounded only in document chunks
retrieved by `hybrid_search`. The roadmap's Phase 8b asks for persistent
memory across conversations — episodic (conversation summaries), semantic
(facts about users/entities/cases), and procedural (reusable workflows) —
retrieved via pgvector and automatically injected into chat.

## Decision

### Schema: one `memories` table, exactly as specified
`api/models.py` gets a `Memory` model / `memories` table: `id`, `user_id` (FK,
cascade delete), `memory_type` (`episodic`/`semantic`/`procedural`, enforced
in application code the same way `Entity.entity_type` is — see ADR 0008 --
not a DB-level enum, since the roadmap's own phase list suggests this set
will grow), `importance` (0-100 int), `summary`, `embedding`
(`Vector(settings.embedding_dim)`, same dimension/model as document chunks —
one Ollama embedding model for the whole system), `json_data` (JSONB, for
type-specific structured extras a summary string doesn't capture), and the
three lifecycle timestamps from the spec. Indexed the same way
`document_chunks` is: HNSW cosine index on `embedding`, plus a plain index on
`user_id` (every retrieval query filters by owner first).

### Retrieval: reuse the existing pgvector pattern, don't build a new one
`api/memory.py::retrieve_relevant_memories` mirrors
`search_service.hybrid_search`'s semantic half: embed the query, `ORDER BY
embedding.cosine_distance(...)`, filter to the requesting user and
non-expired rows (`expires_at IS NULL OR expires_at > now()`). No keyword/BM25
half like document search has — memory summaries are short, LLM-generated
facts, not long documents with distinct passages, so semantic similarity
alone is the right tool. Every retrieval also stamps `last_used_at`, which is
what "expiration" and any future memory-pruning policy would key off.

### Creation: an extraction agent, same shape as the Planner/Entity Agents
`api/memory.py::maybe_create_memory_from_exchange` follows
`planner_agent.py`/`entity_agent.py`'s established pattern exactly: a
JSON-mode prompt asks the model whether this specific exchange revealed
anything durable (a preference, an ongoing matter, an entity fact, a
reusable plan) as opposed to a one-off question, with a `should_remember`
gate, an `importance` score, and a `summary` to embed and store. Malformed
model output is logged and treated as "nothing to remember" -- same
graceful-degradation the other two agents already use.

`chat()` calls this from a `BackgroundTasks` callback after the response is
already built, the same mechanism `documents.py`'s upload endpoint used
before Phase 8a (ADR 0017) introduced the event bus for the ingest
pipeline. This phase is **not** built on top of the (still-unmerged) Phase
8a branch: the roadmap frames 8a-8d as "independently deployable
milestones," so 8b doesn't take a hard dependency on 8a merging first. Once
both are in, routing memory creation through the event bus (e.g. a
`ConversationTurnCompleted` event 8a's `EventType` doesn't have yet) is a
natural follow-up -- but it isn't a prerequisite for 8b's acceptance
criteria today. Using `BackgroundTasks` here means the extra LLM call for
extraction never adds latency to the user-visible chat response, same
reasoning as the original ingest pipeline.

Both the retrieval call and the background extraction call are wrapped in a
`# noqa: BLE001` catch-and-log, the same "a side effect must never fail the
primary flow" rule already applied to Signal notifications and auto
task/entity extraction elsewhere in this codebase (ADR 0004, ADR 0007). A
memory-subsystem hiccup (pgvector, Redis, or the embedding/LLM call
failing) degrades chat to "no memories this turn," never a broken response.

### Retrieval wired into chat, additively
`chat()` now does two retrievals before calling the AI Gateway: the existing
document `hybrid_search`, and `retrieve_relevant_memories`. Memories are
rendered as their own labeled block in the same user-turn message
(`Relevant memories:\n- ...`) rather than merged into the document citation
list -- they're not citable sources with IDs/titles the way document chunks
are, just standing context, the same way prior conversation `history` turns
already are. No memories found is not an error; the block is simply omitted
if empty, same treatment as no document hits.

### Manual deletion and expiration
`DELETE /memories/{id}` (owner or admin, mirroring `documents.py`'s delete
authorization check) — hard delete, no soft-delete/undo, since nothing else
references a memory row (no FK points at `memories`). `expires_at` is
settable at creation time (the extraction agent doesn't set one today --
nothing in the initial memory examples implies a TTL -- but the column and
the retrieval filter both exist so a future extraction rule or a manual
`PATCH` can use it without a schema change). No background reaper: expired
rows are simply excluded from retrieval, which is what the acceptance
criterion actually requires; a periodic hard-delete job is a real but
separate concern (a cron entry, like the existing backup job) with no
current caller asking for it.

### Out of scope for 8b
No memory summarization/consolidation (turning many episodic memories into
fewer semantic ones), no cross-user memory sharing, no admin-facing memory
browser UI, no `PATCH /memories/{id}`. These are real follow-ups once 8c's
planner or real usage patterns ask for them.

## Consequences
- Every chat turn now does one extra pgvector query (cheap, same index
  strategy already proven for `document_chunks`) and, in the background,
  one extra LLM call for extraction -- a real cost/latency tradeoff the
  roadmap accepts implicitly by asking for memory on every conversation.
- `Memory` has no relationships back into `Entity`/`Document` yet;
  `json_data` is where a semantic memory like "Vehicle XX-999-X belongs to
  entity John Doe" would carry a structured entity reference once 8c's
  planner needs to consume it programmatically rather than as prose.
