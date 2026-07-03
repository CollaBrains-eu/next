# ADR 0022: Phase 9b — MCP Platform

## Status
Accepted

## Context

`docs/roadmap/phase-09.md` frames 9b as: "an `mcp/` service exposing the
tool registry over the Model Context Protocol, so tools are callable
the same way from `/chat`, the Planning Engine, and (eventually)
external MCP clients, instead of three different in-process call
conventions." Phase 9a built the registry (`api/tool_registry.py`,
`api/tools.py`, `GET /tools`); 9b's job is to make it reachable over the
actual MCP wire protocol.

## Branching off 9a instead of `main`

Every Phase 8 sub-phase, and 9a, was built independently from `main`,
reconciling conflicts only when merged. 9b breaks that pattern
deliberately: it cannot do anything meaningful without 9a's actual
`ToolDescriptor`/`register_tool`/`dispatch` code existing to expose.
That's a hard code dependency, not just a conceptual one -- Phase 8's
four sub-phases touched non-overlapping or lightly-overlapping surface
and could be reconciled at merge time; 9b's entire purpose is calling
9a's registry. This branches from `phase-9a-tool-registry` (still an
open PR) rather than `main`; once 9a merges, this PR's base will follow
automatically.

## Decision

**A single `POST /mcp` endpoint implementing MCP's Streamable HTTP
transport in its simplest form**: one JSON-RPC 2.0 request in, one
JSON-RPC 2.0 response out, no SSE streaming -- none of the five
registered tools produce server-to-client streaming output, so the
simpler non-streaming shape of the transport is sufficient. Three
methods are handled: `initialize`, `tools/list`, `tools/call`. Anything
else returns a JSON-RPC "method not found" error (`-32601`), the
correct behavior for an unsupported method under the protocol, not a
gap.

**`tools/list` translates `ToolDescriptor.input_schema`'s prose strings
into real JSON Schema.** 9a's descriptors use human-readable values like
`"integer (optional, default 10)"` for `GET /tools`'s benefit (ADR
0021) -- MCP requires actual JSON Schema (`{"type": "integer"}`,
a `required` list) for a real client to construct valid calls.
`api/mcp_server.py`'s `_field_to_json_schema()` does a small, well-tested
translation (first word of the prose maps to a JSON Schema type,
`"(optional"` anywhere in the string excludes it from `required`) rather
than changing 9a's already-reviewed descriptor format retroactively.
This is a deliberately narrow, single-purpose translator, not a general
prose parser -- it's tested directly against all five real registered
tools' actual schemas, not just synthetic cases.

**`tools/call` always derives `user_id` from the authenticated
session, never from the client-supplied `arguments`.** The MCP endpoint
requires the same JWT bearer auth (`get_current_user`) as every other
endpoint in this codebase -- MCP's own spec has an OAuth-based auth
extension, which is out of scope here (documented gap, see
Consequences). Reusing the existing auth mechanism means an MCP caller
can only ever act as the authenticated user, the same invariant every
other endpoint already enforces, and is what makes this safe to expose
today even though Phase 9c's finer-grained tool permissions don't exist
yet: an authenticated MCP client calling a tool gets exactly what that
same user could already do through the tool's equivalent existing HTTP
endpoint (`/search`, `/documents/{id}/summarize`, `/legal/draft`,
`/documents/{id}/extract-tasks`, `/documents/{id}/extract-entities`) --
this is not a new exposure, just a new transport for an existing one.
This is why 9a's "no raw dispatch over HTTP until 9c" caution doesn't
block 9b: 9a's concern was a tool-permission model that doesn't exist
yet being silently bypassed; here, every wrapped tool already has an
equivalent authenticated endpoint doing the same thing with the same
(lack of) fine-grained permission checking, so MCP grants no new
capability.

**A tool execution error is a JSON-RPC *success* response with
`result.isError: true`**, per MCP convention -- distinct from a
protocol-level JSON-RPC error (malformed request, unknown method).
`dispatch()` raising `KeyError` (unknown tool) or `ValueError` (e.g.
`summarize_document` on a not-ready document) both map to this, not to
a JSON-RPC error object.

**`/chat`, the Planning Engine, and Legal endpoints are not refactored
to call through MCP or `dispatch()` in this slice.** The roadmap
description of "tools callable the same way from /chat, the Planning
Engine, ..." describes Phase 9's eventual end state across all four
sub-phases, not a requirement for 9b specifically. Rewiring existing,
already-tested production call paths onto a new protocol boundary is a
separate, higher-blast-radius change than adding a new one -- deferred
the same way 9a deferred calendar/mail tools and raw HTTP dispatch.

## Consequences

- A real external MCP client (Claude Desktop, another agent) could
  connect to `POST /mcp` today, given a valid JWT, and call any of the
  five registered tools -- proving the "eventually: external MCP
  clients" half of the roadmap's framing, ahead of 9c/9d.
- **Known gap, deliberately deferred**: MCP-standard OAuth-based
  discovery/auth is not implemented; a real external client needs to be
  handed a JWT out-of-band today, the same way any other API consumer
  of this codebase does. Worth revisiting once there's a second real
  external MCP client to design against, not speculatively now.
- `_field_to_json_schema()`'s prose-to-schema translation is inherently
  lossy for anything more structured than "string/integer/boolean/array
  (optional)" -- if a future tool's input genuinely needs nested object
  schemas, that's the point where `ToolDescriptor.input_schema` should
  probably become real JSON Schema natively rather than prose, and this
  translator retired. Not needed for the five tools that exist today.
