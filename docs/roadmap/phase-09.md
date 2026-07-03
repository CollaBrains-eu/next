# Phase 9 — AI Platform

> **Status: done.** Built as 9a Tool Registry (ADR 0021), 9b MCP
> Platform (ADR 0022), 9c Permissions (ADR 0023), 9d Tool Discovery
> (ADR 0024) — see `README.md` for the summary and those ADRs for what
> actually shipped vs. what this spec originally proposed. Kept here as
> historical context for how the open design questions below got
> resolved.

## Goal

Stop hardcoding which tools exist into each agent. Every capability the
AI can use (search, Signal, Paperless, calendar, mail, entity
extraction, planning, ...) becomes a self-describing tool that the AI
discovers and calls through a common registry, instead of Python code
explicitly wiring "the Legal Agent calls `hybrid_search`, the Planner
Agent calls `extract_tasks`" one function at a time.

## Why now

Phases 1-8 added agents by writing more Python that calls more Python.
That works while there are a handful of agents and a handful of tools,
but it doesn't scale to Phase 11's Multi-Agent System, where a Manager
Agent needs to choose *at runtime* which tool a given agent is allowed
to use for a given task — that requires tools to be inspectable data,
not just import statements.

## Structure

Four independently deployable sub-phases, same discipline as Phase 8:

- **9a — Tool Registry**: a `tool_registry/` module holding a list of
  tool descriptors (name, description, input schema, output schema,
  required permissions) and a lookup/dispatch API. Existing agent
  functions (`hybrid_search`, `extract_tasks`, `extract_entities`,
  `_generate_draft`, `_generate_summary`, ...) get registered as tools
  rather than rewritten — this phase is about the registry and
  descriptors, not re-implementing working code.
- **9b — MCP Platform**: an `mcp/` service exposing the tool registry
  over the Model Context Protocol, so tools are callable the same way
  from `/chat`, the Planning Engine, and (eventually) external MCP
  clients, instead of three different in-process call conventions.
- **9c — Permissions**: each tool descriptor's `permissions` list is
  enforced against the calling user's role/scopes before dispatch —
  reuses the existing `role` field on `User` (ADR 0001) rather than
  introducing a new authorization model.
- **9d — Tool Discovery**: the AI Gateway can list available tools and
  their schemas at call time (an MCP-style `list_tools`), so a prompt
  can be built from "here's what you can call" rather than a fixed
  system prompt enumerating tools by hand.

Proposed layout:

```
tools/
    signal/
    paperless/
    planner/
    entity/
    search/
    postgres/
    calendar/
    mail/
tool_registry/
permissions/
mcp/
```

Each tool describes itself, e.g.:

```yaml
name: search
description: Search indexed documents.
permissions:
  - documents.read
input:
  query: string
output:
  documents: []
```

## Open design questions (resolve at 9a implementation time)

- Do existing endpoints (`/search`, `/legal/draft`, ...) stay as they
  are and *also* get registered as tools, or do they become thin
  wrappers over a tool-registry call? (Likely the former to start,
  same "don't rewrite working code" reasoning as Phase 8c's
  `_generate_summary`/`_generate_draft` extraction — register first,
  refactor later only if duplication actually becomes a problem.)
- Where do calendar and mail tools' underlying integrations live? They
  don't exist yet in this codebase — 9a should scope down to
  registering *existing* tools only, and treat net-new integrations
  (calendar, mail) as their own follow-up slice once the registry
  itself is proven.

## Acceptance criteria

- A tool can be added by writing a descriptor + implementation under
  `tools/`, with no changes to `api/main.py` or any agent's code.
- Calling a tool the AI isn't permitted to use is rejected before
  dispatch, not caught as a downstream error.
- At least one existing capability (e.g. `hybrid_search`) is served
  through the registry end-to-end, proving the pattern before more
  tools are migrated.
