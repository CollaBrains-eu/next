# ADR 0026: Phase 11 — Multi-Agent System

## Status
Accepted

## Context

`docs/roadmap/phase-11.md` frames this phase as a Manager Agent that
"chooses which agent handles a request... instead of the calling code
deciding," and names it as depending on Phase 9's Tool Registry (done).
It leaves three open design questions: whether the Manager itself calls
an LLM to choose, what replaces Planning Engine's fixed templates, and
how a failed selection surfaces.

## Decision

**The model itself is the Manager; there is no separate "Manager Agent"
abstraction, capability descriptor, or agent-cost/priority model.**
Phase 9d's `chat_completion_with_tools()` + `to_ollama_tools()` already
built the exact mechanism this phase needs: offer the model a set of
callable tools, let it decide (via Ollama's native function-calling)
which one applies to a given natural-language request, and return that
choice. `docs/roadmap/phase-11.md`'s question "does the Manager call an
LLM, or is it deterministic capability-matching" is answered: an LLM,
because that's what makes "instead of the calling code deciding"
actually true -- a deterministic capability-matcher over a
natural-language request is still the calling code deciding, just
dressed up. This also means no new `Agent` descriptor with declared
Capabilities/Memory/Allowed-tools/Cost/Priority fields -- `ToolDescriptor`
(9a) already is the capability declaration; a parallel `Agent` type
with speculative `cost`/`priority` fields nothing in this codebase
differentiates on yet would be exactly the kind of premature structure
ADR 0023 already declined for `member`/`admin` permissions.

**This closes the loop 9d explicitly left open, and nothing else.** ADR
0024 said executing a model-requested tool call -- "request, dispatch,
re-prompt with the result" -- was Phase 11 territory. `api/manager_agent.py`
does exactly that, one round: call the model with tools, if it requests
one, `dispatch()` it (reusing 9a's registry and 9c's permission
enforcement unchanged), feed the result back, get a final answer. No
multi-round agentic looping (call a tool, then decide to call another,
...) -- that's `docs/roadmap/phase-12.md`'s "Autonomous Workflows"
observe/plan/execute/verify/learn territory, not this phase's.

**Tools are filtered by the calling user's permissions before being
offered to the model.** ADR 0024 noted `to_ollama_tools()` lists every
registered tool regardless of role, and explicitly left "filtering by
the same `has_permission()` check" as a caller concern. This is that
caller: `api/manager_agent.py` builds the offered tool list from
`list_tools()` filtered by `has_permission(role, tool.permissions)`,
then converts only the permitted subset to Ollama's format. The model
is never shown a tool it isn't allowed to invoke, rather than being
shown it and failing at dispatch time.

**A tool execution error is fed back to the model as the tool result,
not raised.** `dispatch()` raising `ValueError` (e.g. `summarize_document`
on a not-ready document) is caught and turned into an error string
handed back the same way a successful result would be -- the model can
respond sensibly ("that document isn't ready yet") instead of the
request crashing. `KeyError`/`ToolPermissionError` shouldn't occur in
practice since the model only ever sees permitted, real tool names, but
are caught the same way as a defensive measure, not assumed impossible.

**Planning Engine (8c) is untouched.** Its fixed goal templates keep
working exactly as before -- this phase adds a new, separate,
single-turn "ask" capability (`POST /manager/ask`) alongside the
existing structured multi-step `POST /plans`, not a replacement for it.
Answers `docs/roadmap/phase-11.md`'s second open question directly.

**`POST /manager/ask` uses `get_current_user`, not `get_effective_user`.**
Unlike `/chat`, this is a new capability without an established
Signal on-behalf-of caller yet -- narrower auth for the first slice,
matching the "don't build for a caller that doesn't exist yet" pattern
elsewhere in this project (e.g. 9a deferring calendar/mail tools).

**Verified via mocked `chat_completion`/`chat_completion_with_tools`
calls, same as every other AI Gateway caller's tests in this codebase**
(`test_chat.py`, `test_tools.py`, `test_ai_gateway.py` itself) -- no
test here calls a live Ollama instance. Whether the currently configured
`qwen2.5:3b-instruct` model reliably honors tool-calling in practice
(rather than just responding in prose) is a real operational question
unit tests can't answer; worth a manual live check once deployed, not
blocking this PR the way it hasn't blocked any earlier AI Gateway work.

## Consequences

- A user can now ask a free-form question and have the system
  autonomously decide to search documents, draft a legal document,
  extract tasks, or extract entities on their behalf -- the first place
  in this codebase where tool selection isn't hardcoded per-endpoint.
- Multi-round tool use, a real "Manager chooses among multiple
  candidate agents with different cost/priority" model, and wiring this
  into `/chat` itself (today `/chat` still only ever retrieves documents
  directly, unchanged) are all deferred, not solved speculatively.
- If the configured model doesn't reliably produce well-formed
  `tool_calls`, the single-round design degrades gracefully: no tool
  call means the model's own prose becomes the answer directly, the
  same as if tools were never offered.
