# ADR 0024: Phase 9d — Tool Discovery

## Status
Accepted

## Context

`docs/roadmap/phase-09.md` frames 9d as: "the AI Gateway can list
available tools and their schemas at call time (an MCP-style
`list_tools`), so a prompt can be built from 'here's what you can call'
rather than a fixed system prompt enumerating tools by hand." This is
the last of Phase 9's four sub-phases (9a Tool Registry #6, 9b MCP
Platform #7, 9c Permissions #8, 9d — this PR).

## Branching off 9c instead of `main`

Same reasoning as 9b off 9a and 9c off 9b: 9d reuses 9b's JSON-Schema
translation logic (moved here, see below) and adds to the same AI
Gateway every other phase already depends on. Branches from
`phase-9c-permissions`; bases follow automatically as 6/7/8 merge.

## Decision

**"A prompt can be built from tools" means Ollama's native
function-calling `tools` parameter, not hand-formatted prompt text.**
Ollama's `/api/chat` accepts an OpenAI-style `tools` array
(`{"type": "function", "function": {"name", "description",
"parameters"}}`); the currently configured model
(`qwen2.5:3b-instruct`, ADR 0003) supports it. This is a more direct
realization of "here's what you can call" than manually stitching tool
descriptions into system-prompt text -- the model receives structured
tool definitions the same way any OpenAI-compatible client would, and
can respond with a structured `tool_calls` array instead of prose
describing what it wants to do.

**`api/ai_gateway.py` gets a new `chat_completion_with_tools()`
function, not a `tools` parameter bolted onto `chat_completion()`.**
`chat_completion()`'s contract (`messages -> str`) is used by every
existing caller in the codebase (`chat.py`, `legal.py`, `documents.py`,
`entity_agent.py`, `planner_agent.py`, `memory.py`, `reflection.py`);
changing its return shape conditionally on whether `tools` was passed
would be a real type-safety smell. Both functions now share a new
private `_call_ollama()` helper (rate limit, request, audit log --
exactly `chat_completion`'s previous body, unchanged behavior) that
returns the raw response message dict; `chat_completion()` extracts
`["content"]` from it (same public contract as before, zero blast
radius on any existing caller); `chat_completion_with_tools()` returns
the whole message so a caller can inspect `message.get("tool_calls")`.

**`api/tool_registry.py` gains `to_ollama_tools()`, and the JSON-Schema
translator moves here from `api/mcp_server.py`.** 9b's
`_field_to_json_schema`/`_input_schema_to_json_schema` already produce
exactly the JSON Schema shape both MCP's `inputSchema` and Ollama's
`parameters` need -- the same translation, two different wrapper
shapes. Moving the translator to `tool_registry.py` (the lower-level
module both `mcp_server.py` and the new `to_ollama_tools()` depend on)
avoids duplicating it and avoids a circular import (`mcp_server.py`
already imports from `tool_registry.py`; the reverse would break at
import time). `mcp_server.py`'s own `_tool_to_mcp_schema()` wrapper
stays where it is -- only the shared translator moved.

**Executing a model-requested tool call is explicitly out of scope
here.** `chat_completion_with_tools()` returns the tool call request;
it does not look it up in the registry, call `dispatch()`, or feed a
result back for a second round-trip. That loop -- request, dispatch,
re-prompt with the result -- is autonomous tool use, which is Phase 11
(Multi-Agent System)/Phase 12 (Autonomous Workflows) territory per the
roadmap's own phase boundaries, not "discovery." Wiring `/chat` or the
Legal Agent to actually call tools this way is the same kind of
deferred, higher-blast-radius rewiring ADR 0022/0023 already declined
for MCP -- still true here.

## Consequences

- A future caller (most plausibly Phase 11's Manager Agent) can call
  `chat_completion_with_tools(messages, tools=to_ollama_tools(), ...)`
  and get back a real, structured tool-call request today, with no
  further Phase 9 work needed -- 9d's job was making that possible, not
  building the loop that consumes it.
- `to_ollama_tools()` reflects 9c's permissions implicitly through
  nothing at all: it lists every registered tool regardless of any
  particular user's role. A caller that hands the model a tool it
  can't actually invoke (because 9c's `dispatch()` will reject it) will
  get a `ToolPermissionError` at dispatch time, same as any other
  caller -- scoping *which* tools to offer a given user is a caller
  concern (e.g. filtering `to_ollama_tools()`'s output by the same
  `has_permission()` check 9c added), not something this function does
  itself, since it has no calling-user context to filter by.
- `chat_completion()`'s existing tests and every existing caller are
  unaffected -- verified by running the full suite, not just by
  inspection.
