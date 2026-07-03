# ADR 0023: Phase 9c — Permissions

## Status
Accepted

## Context

9a recorded `permissions: list[str]` on each `ToolDescriptor` but never
enforced it (ADR 0021); 9b explicitly reused that gap's reasoning to
justify exposing `dispatch()` over MCP without enforcement (ADR 0022:
"MCP grants no new capability... fine-grained tool permission
enforcement is still Phase 9c's job"). This ADR closes that gap.

`docs/roadmap/phase-09.md` frames 9c as: "each tool descriptor's
permissions list is enforced against the calling user's role/scopes
before dispatch — reuses the existing `role` field on `User` (ADR 0001)
rather than introducing a new authorization model."

## Branching off 9b instead of `main`

Same reasoning as 9b branching off 9a (ADR 0022): enforcement lives
inside `dispatch()`, which is 9a's code, and the one existing caller of
`dispatch()` today is 9b's `handle_tools_call` — this PR needs to catch
the new exception type there too. Branches from `phase-9b-mcp-platform`;
bases will follow automatically once 9a and 9b merge.

## Decision

**A static `role -> frozenset[str]` mapping (`api/permissions.py`), no
new tables, no per-user overrides.** Reuses `User.role`
(`member`/`admin`/`service`, ADR 0001) exactly as the roadmap specifies.

```python
ROLE_PERMISSIONS = {
    "member": frozenset({"documents.read", "legal.draft", "tasks.write", "entities.write"}),
    "admin": frozenset({"documents.read", "legal.draft", "tasks.write", "entities.write"}),
    "service": frozenset(),
}
```

**`member` and `admin` currently grant identical permission sets.** This
looks redundant but is deliberately true to today's actual authorization
state: none of the five existing tools' equivalent HTTP endpoints
(`/search`, `/legal/draft`, `/documents/{id}/summarize`,
`/documents/{id}/extract-tasks`, `/documents/{id}/extract-entities`)
are role-gated today — any authenticated user can call all of them.
Making `legal.draft` or any other permission admin-only right now would
be a real behavior regression, not a security improvement, since it
would restrict something currently open to every authenticated user
based on a role split this project has never actually enforced
anywhere. The mapping exists so a *future* admin-only tool has
somewhere to declare that, not because these two roles need different
scopes for the tools that exist today.

**`service` gets zero permissions by default.** Service accounts
(ADR 0006: the Signal bot's on-behalf-of caller) have never called any
of these five tools directly — they're used for `/chat`'s on-behalf-of
resolution only. Granting zero permissions is the conservative default;
revisit if a real service-account tool-calling need emerges (same
"defer until a second real consumer" reasoning as 9a's calendar/mail
tools and 9b's OAuth gap).

**Enforcement lives inside `dispatch()` itself, not in each call site.**
`dispatch()` is the one chokepoint every tool call already goes
through — checking there means a caller cannot forget to check
permissions, unlike passing a `role` string as an explicit parameter a
future caller could get wrong (or, if trusted from client input, spoof).
`dispatch()` still takes `**kwargs` only (unchanged signature from 9a) --
it reads `db`/`user_id` out of the kwargs that real tool calls already
always pass (every handler needs them anyway), fetches the `User` row
itself, and checks its role against the tool's `permissions`. This keeps
9a's and 9b's existing tests that register permission-less throwaway
tools (`permissions=[]`, no `db`/`user_id` needed) completely
unaffected -- the permission check only activates when
`tool.permissions` is non-empty, which today means exactly the five
real built-in tools plus none of the temp test tools.

**A new `ToolPermissionError`** (in `api/tool_registry.py`, alongside
`dispatch()`) is raised on: missing `db`/`user_id` for a
permission-requiring tool, an unknown `user_id`, or a role lacking the
required permissions. `api/mcp_server.py`'s `handle_tools_call` catches
it alongside the existing `KeyError`/`ValueError` and reports it the
same way -- a JSON-RPC success response with `result.isError: true`,
per MCP convention (a permission denial is still a valid call that
failed for a reason, not a malformed request).

**Existing tests updated, not left broken.** Four of 9a's
`test_tools.py` tests and one of 9b's `test_mcp_server.py` tests called
`dispatch()`/`handle_tools_call()` with `db=None` for tools that now
require a real `db` to check permissions -- fixed to use a real session,
since that's what these tools' actual callers (the MCP router) always
provide anyway. This is a necessary, expected ripple from enforcement
actually existing now, not a design flaw being patched over.

## Consequences

- Any future tool with a `permissions` entry no role currently grants
  is unreachable until `ROLE_PERMISSIONS` is updated -- a deliberate
  fail-closed default, not an oversight.
- `GET /tools` (9a) is unchanged -- it lists what tools exist, not
  whether the calling user can invoke them. Surfacing per-user
  reachability is Tool Discovery's job (9d), not this phase's.
- `/chat`, the Planning Engine, and Legal endpoints still call their
  underlying functions directly, not through `dispatch()` -- this
  phase's permission enforcement has no effect on them, same scoping
  note as ADR 0022.
