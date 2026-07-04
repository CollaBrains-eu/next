# ADR 0034: Phase 17c — Manager Agent / Assistant UI

## Status
Accepted

## Context

The Phase 11 Manager Agent (`POST /manager/ask`, ADR 0026) is the only
place in this codebase where tool selection isn't hardcoded per
endpoint — it's an Ollama-native function-calling loop that picks a
registered tool (search, summarize, draft, extract tasks, extract
entities) per request. It had no UI before this sub-phase; only
`/chat` (RAG + citations + memory) existed. Phase 17
(`docs/superpowers/specs/2026-07-04-frontend-catchup-design.md`) gives
it one: `/assistant`, built on the Phase 17a sidebar shell.

## Decision

**`/assistant` is a separate page, not a mode toggle inside `/chat`.**
The two backend capabilities are genuinely different: `/chat` answers
only from retrieved document context and resends full visible history
every turn (stateless server, client-carried history); `/manager/ask`
takes only the current message and may call a tool instead of just
answering from documents. Conflating them behind one toggle would blur
what's actually happening on each request.

**The local turn list is display-only.** Unlike `Chat.tsx`, which
resends the full visible history as context every request,
`Assistant.tsx` sends only `{ message }` per `POST /manager/ask` —
matching the endpoint's actual stateless, single-round contract (ADR
0026). The on-screen running list exists purely for readability, not
because the backend has any memory of it.

**A `tool_called` badge renders under any response where a tool fired.**
The entire point of exposing this UI is to make the Manager Agent's
tool selection observable rather than a black box — a plain
`via: <tool_name>` line under the assistant's bubble, only when
`tool_called` is non-null.

## Consequences

- No backend changes were needed — `POST /manager/ask` already existed
  and needed no modification.
- No component-level test coverage was added for `Assistant.tsx` — same
  reasoning as 17a/17b: no React component testing library in this
  codebase. Verified via `tsc -b` plus a live browser check that
  triggers a real tool call.
