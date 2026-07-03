# ADR 0010: Phase 5b Frontend — Chat, Legal Draft, Task UI

## Status
Accepted

## Context
Phase 5a shipped auth, the app shell, and the document library. Phase 5b
is the second slice of the Phase 5 split (see ADR 0009): it adds UI for
the three remaining request/response agents that were already fully
functional server-side since Phases 2a/2b — the Orchestrator (`POST
/chat`), the Legal Agent (`POST /legal/draft`), and the Planner Agent
(`GET/PATCH /tasks`). None of these needed new backend work; this phase
is purely frontend.

## Decisions

**Chat (`/chat` route, rewrites the Phase 0 placeholder)**: a standard
message-list + input UI. Each `POST /chat` call sends the full visible
history (the backend is stateless per ADR 0003 — no server-side
conversation memory), and each assistant reply renders its `citations`
as a small footer list of document links using the `[n]` markers already
embedded in the answer text. No streaming — `chat_completion()` in the
AI Gateway is a single blocking call, and adding SSE/websocket streaming
is a backend change out of scope for a frontend-only phase; the CPU-only
qwen2.5:3b model takes a few seconds per reply, acceptable for now.

**Legal draft (`/legal` route, new)**: an instruction textarea, an
optional multi-select of documents to scope retrieval to (via
`document_ids`), and a submit that renders the returned draft text,
citations, and the disclaimer the backend always returns. Deliberately
one-shot (no chat-style back-and-forth) — `POST /legal/draft` isn't
multi-turn, so a chat UI here would misrepresent the endpoint's contract.

**Tasks (`/tasks` route, new)**: a flat list of tasks (title,
description, due date, assignee, status) with a status filter
(open/done) and a checkbox-style toggle that calls `PATCH /tasks/{id}`.
No document-scoped view or manual task creation in 5b — `GET /tasks`
already returns everything the Planner Agent extracted across all
documents, and manual task creation isn't a capability the backend
exposes yet (tasks are only ever agent-extracted, per ADR 0004).

**Navigation**: adds "Legal Draft" and "Tasks" to the top nav alongside
the existing "Documents" and "AI Chat" links.

## Why not more in 5b
Streaming chat, task creation/deletion, and citation-source preview
panels are all real backend or UX work beyond "expose what already
exists," and are deferred until there's a concrete need. The entity
graph visualization remains Phase 5c, unaffected by this phase.
