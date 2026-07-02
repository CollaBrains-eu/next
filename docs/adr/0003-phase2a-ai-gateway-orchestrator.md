# 0003: Phase 2a — AI Gateway, Orchestrator, Document & Search Agents

## Status
Accepted (2026-07-02)

## Context
The original brief scopes Phase 2 as: AI Gateway, AI Orchestrator, and four
agents (document, legal, planner, search — per the existing stub READMEs in
`agents/*`). That's substantially more than one coherent unit of work: legal
reasoning/objection drafting and task planning/scheduling are each
distinct, domain-specific capabilities that deserve their own design pass,
not a rushed implementation bolted onto the infrastructure pieces.

Following the same pattern used for Phase 1 (split into 1a/1b), Phase 2 is
split:

- **2a (this ADR)**: AI Gateway, AI Orchestrator, Document Agent, Search
  Agent — the foundational "ask a question, get a grounded answer" RAG-chat
  capability, built directly on Phase 1b's document/search pipeline.
- **2b (deferred)**: Legal Agent, Planner Agent — revisit once 2a's agent
  pattern exists to build on, and once these get a proper design pass.

## Decisions

### Still a monolith: no new deployable services
Per ADR 0001, only `services/api` has real code; `services/ai-gateway` and
`services/ai-orchestrator` stay scaffolded stubs, same as `services/auth`
and `services/documents` did before Phase 1a/1b landed inside `services/api`
instead. AI Gateway and Orchestrator are implemented as modules
(`api/ai_gateway.py`, `api/chat.py`) inside the existing API service. This
avoids a second FastAPI process, a second Dockerfile, and inter-service
auth for a capability with exactly one caller so far. Revisit if/when
Signal (Phase 3) or another client needs to call the AI layer without going
through the main API.

### Chat model: Ollama `qwen2.5:3b-instruct`
Tested directly on this host before committing: ~22 tokens/sec on CPU
(8 vCPU, no GPU), fast enough for interactive chat, and produced a
correct, well-formed answer to a test RAG-style question. A larger model
(7B+) would noticeably slow down interactive use with no compensating
benefit at this stage.

### AI Gateway responsibilities (scoped down from the stub's full list)
`api/ai_gateway.py` provides: a single `chat_completion()` call over
Ollama, per-user rate limiting (fixed-window, Redis-backed — Redis is
already running and otherwise unused), and an audit log
(`ai_call_log` table: user, endpoint, model, token counts, duration) for
every call. "Auth" and "model selection" are handled by reusing the
existing JWT dependency and a single configured default model — a
multi-model routing layer isn't needed yet with one model in play.

### Orchestrator: retrieval-augmented `/chat`, not a free-form planner
`POST /chat` takes a user message, retrieves relevant chunks via the
Search Agent (see below), builds a grounded prompt with citations, and
calls the AI Gateway. There is no autonomous multi-step planning or
free-form tool selection — that level of agent autonomy belongs to the
Planner Agent (2b). The orchestrator's only current "routing" decision is
always the same: retrieve, then answer.

**No server-side conversation memory yet.** The brief's "memory" line item
for the orchestrator is real scope, but persisted multi-turn conversation
history is a separate feature (threading, storage, retention) worth its
own decision, not a rushed add-on here. `/chat` accepts prior turns from
the caller (client-side history) and stays stateless server-side. Revisit
once there's a concrete multi-turn UX to build against.

### Search Agent: existing hybrid search, not a new thing
The Phase 1b `/search` endpoint's reciprocal-rank-fusion logic is
extracted into a reusable `hybrid_search()` function in
`api/search_service.py`, used by both the `/search` endpoint and the
orchestrator's retrieval step. This *is* the Search Agent — it doesn't
need a separate identity beyond that shared function; introducing an
"agent" abstraction/base class for a single call site would be premature.

### Document Agent: summarization
One concrete capability: `POST /documents/{id}/summarize`, an LLM-generated
summary of a single document's OCR text via the AI Gateway, cached on
`documents.summary` so repeat calls don't re-run inference. Further
document-agent capabilities (classification, redaction, etc.) can be added
as their own endpoints later without changing this shape.

### Auditability
Every AI Gateway call is logged (`ai_call_log`) with the user, model, token
counts, and duration — supports the brief's security/audit requirements
and gives real usage data to inform Phase 2b sizing decisions (e.g.,
whether the 3B model is holding up under real load).
