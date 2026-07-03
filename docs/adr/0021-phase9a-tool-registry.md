# ADR 0021: Phase 9a — Tool Registry

## Status
Accepted

## Context

`docs/roadmap/phase-09.md` frames Phase 9 as making the AI's capabilities
self-describing and discoverable instead of hardcoded into each agent's
Python — a prerequisite for Phase 11's Manager Agent, which needs to
reason about "what can I call" as data, not by reading source code.

Phase 9 splits into four independently deployable sub-phases (9a Tool
Registry, 9b MCP Platform, 9c Permissions, 9d Tool Discovery), same
discipline as Phase 8. This ADR covers 9a only.

## Decision

**A tool is a descriptor plus a handler, registered at import time; no
new tool implementation logic, no rewritten agents.** Five existing
capabilities get wrapped as tools:

| Tool | Wraps |
|---|---|
| `search` | `api.search_service.hybrid_search` |
| `summarize_document` | `api.documents._generate_summary` |
| `draft_legal_document` | `api.legal._generate_draft` |
| `extract_tasks` | `api.planner_agent.extract_tasks` |
| `extract_entities` | `api.entity_agent.extract_entities` |

Each is a thin wrapper converting primitive/JSON-friendly input (IDs,
strings) to what the underlying function needs and its output back to a
plain dict — the existing functions are not modified, imported and
called exactly as the Planning Engine (ADR 0019) already imports
`_generate_summary`/`_generate_draft`. This is the same "register first,
refactor later only if duplication becomes a real problem" call
`docs/roadmap/phase-09.md` flagged as the open question here.

**No new repo-level `tools/`/`tool_registry/`/`permissions/`/`mcp/`
top-level directories yet.** The roadmap doc's proposed layout is the
eventual target shape once Phase 9's four sub-phases and Phase 11's
Manager Agent are further along and a second real consumer justifies
the bigger structural move. For 9a alone, `api/tool_registry.py` (the
registry: descriptors, `register`, `get_tool`, `list_tools`, `dispatch`)
and `api/tools.py` (the five registrations above) inside the existing
`services/api/src/api/` package are the smallest safe slice — consistent
with every other phase's package-per-concept convention
(`api/planning_engine.py`, `api/reflection.py`, `api/memory.py`, ...),
not a monorepo-wide reorganization this phase doesn't need yet.

**Permissions are recorded, not enforced, in 9a.** Each `ToolDescriptor`
carries a `permissions: list[str]` field (e.g. `["documents.read"]`),
matching the roadmap doc's descriptor shape, but `dispatch()` does not
check it against the calling user's role — that's explicitly 9c's scope.
Enforcing it now, ad hoc, ahead of 9c's actual permission model would
mean re-doing it once 9c lands with a real design; recording the
metadata without enforcing it costs nothing today and unblocks 9c to
consume it directly.

**`dispatch()` is not exposed as a raw HTTP endpoint in 9a.** A generic
`POST /tools/{name}/call` reachable by any authenticated user, before
9c's permission enforcement exists, would let a `member` invoke a tool
its descriptor marks as requiring a permission it doesn't have — a real
security gap, not just an incomplete feature. 9a adds a read-only
`GET /tools` (list registered tools' name/description/schemas/
permissions, for visibility and to prove the discovery half of the
pattern) but dispatch is an in-process Python API only, for future
callers (Phase 11's Manager Agent, or direct use within this repo) until
9c exists.

## Consequences

- Adding a new tool going forward means writing a descriptor + (if
  needed) a thin wrapper, not touching `api/main.py` or any agent's
  code — the acceptance criterion the roadmap doc names for 9a.
- `GET /tools` gives a first concrete, inspectable answer to "what can
  the AI do," ahead of 9d's fuller "Tool Discovery" (which the roadmap
  scopes as feeding this into prompt construction, not just an
  inspection endpoint).
- Calendar and mail tools named in the roadmap's example layout are
  deliberately out of scope here — they don't have underlying
  integrations to wrap yet; 9a only registers capabilities that already
  exist, per the roadmap doc's own scoping note.
- The five wrapped tools all take a `db: AsyncSession` execution-context
  parameter that isn't part of their JSON-facing `input_schema` — this
  mirrors how every phase so far threads a DB session, not a new
  convention invented for this ADR.
