# Unified chat consolidation + phone-at-creation — Design

## Status

Proposed (awaiting spec review)

## Context

CollaBrains currently has three separate AI-interaction surfaces:

- **`/chat`** (`Chat.tsx`) — hard-constrained to answer only from
  retrieved document content via hybrid search, refuses out-of-scope
  questions, always cites sources. No tool-calling. Supports Signal
  callers via `get_effective_user`.
- **`/legal/draft`** (`Legal.tsx`) — one-shot (not conversational)
  legal drafting scoped to selected documents, always shows an
  attorney-review disclaimer. No tool-calling.
- **`/manager/ask`** (`Assistant.tsx`) — the Manager Agent (Phase 11,
  ADR 0026). Real Ollama function-calling against a
  permission-filtered tool registry (`create_case`, `lookup_vehicle`,
  etc.), **at most one tool call per request** (multi-round chaining
  was explicitly deferred as future scope). Uses `get_current_user`
  only — no Signal support; the router's own docstring names this as
  the reason.

Signal (`apps/signal-bot`) bridges only to `/chat`, so Signal users
never get tool-calling. Phone-number linking is self-service only,
via `PUT /auth/me/phone` after first login — the admin user-creation
form (`POST /admin/users`) has no phone field, and the Postgres `User`
row it eventually produces doesn't exist until first LDAP login
(`_get_or_provision_user` in `auth.py`), so there's currently nowhere
to attach a phone number before that point.

This design was arrived at through a multi-turn Q&A (see the
conversation this spec was extracted from for the full reasoning);
the answers below reflect explicit decisions already made, not open
questions.

## Goals

1. One chat surface, fully generic — no page-level "mode." The
   Manager Agent decides what to do from the message alone.
2. Multi-round tool-calling — the agent can chain several tool calls
   to satisfy one compound request (e.g. "look up this plate, then
   draft a letter to the owner").
3. Signal uses the same backend as the web UI — same tools, same
   grounding/disclaimer guarantees.
4. Admin can set a new user's phone number at creation time; anyone
   left without one gets a one-time, skippable onboarding prompt.

## Non-goals

- Not building a general-purpose plugin/skill marketplace — the tool
  registry mechanism already exists (`tool_registry.py`) and is
  reused as-is, just extended with two more entries.
- Not changing how `preferred_language` drives AI response language
  (`preferences.build_language_instruction`) — unrelated, unaffected.
- Not making the onboarding phone prompt mandatory — explicitly
  rejected in favor of skippable, to avoid locking out existing users
  with no phone number on their next login.

## Architecture

### Phase 1 — Multi-round Manager Agent + two new tools

**File:** `services/api/src/api/manager_agent.py`

`handle_request()` changes from "call the model, dispatch at most one
tool, call the model again for a final answer" to a bounded loop:

```
messages = [system, user]
tools_called = []
for round in range(MAX_TOOL_ROUNDS):  # MAX_TOOL_ROUNDS = 5
    response = chat_completion_with_tools(messages, tools=tools)
    if no tool_calls in response:
        return {"answer": response.content, "tools_called": tools_called, ...}
    call = response.tool_calls[0]  # still one call dispatched per round
    result = dispatch(call) or {"error": ...} on failure
    messages += [assistant-tool-call-msg, tool-result-msg]
    tools_called.append(call.name)
# cap hit without a final answer:
return {"answer": "<couldn't finish in the allowed steps, here's what I found: ...>", "tools_called": tools_called, ...}
```

Per-round error handling is unchanged from today: a failed dispatch
(`KeyError`/`ValueError`/`ToolPermissionError`) becomes an `{"error":
...}` tool-result fed back to the model, which can retry differently
or explain the failure in its final answer — this already works for
one round, the loop just repeats it.

**Cost, stated plainly:** this host's own load-testing (ADR 0015)
measured a single generation at ~23-85s depending on concurrency. A
full 5-round chain is bounded but can take minutes. The frontend's
existing `useLoadingBar` (`start()`/`done()`) already covers the
"still working" indicator — no new UI infrastructure needed, but
users will see long waits on compound requests.

**New tool: `search_documents_grounded`**
- Schema: `{query: string}`.
- Implementation: calls the same hybrid-search function `/chat`
  already uses; returns retrieved chunks + citation metadata as the
  tool result.
- Grounding preserved at the tool level, not the page level: the
  tool's registry description carries a strong "only answer from
  what this tool returns, say so if nothing is relevant" instruction,
  **and** the `chat_completion()` call made immediately after this
  specific tool fires gets that same instruction appended to its
  context — not left to the model to remember from a generic system
  prompt.

**New tool: `draft_legal_document`**
- Schema: `{instruction: string, document_ids?: string[]}` —
  `document_ids` omitted means "all documents," matching today's
  no-checkboxes-selected behavior. Since there's no more checkbox UI,
  the model has to resolve titles mentioned in the message to IDs
  itself: the tool's registry description includes a compact
  `{id, title}` list of the caller's documents directly in its
  schema/description text (small enough to inline — this project's
  existing document counts don't approach a size where that stops
  being cheap; `lookup_vehicle` already sets the precedent of tools
  taking human-readable identifiers rather than requiring a separate
  resolution step). If titles don't match confidently, the model
  omits `document_ids` and falls back to "all documents," same as
  today's no-selection behavior.
- Returns a structured result: `{draft, citations, disclaimer}`. The
  disclaimer is a **data-shape guarantee** attached to the tool's
  result, not prose the model has to remember to include — compliance
  doesn't depend on model behavior.

**`AskResponse` shape change** (`manager_router.py`):
```python
class AskResponse(BaseModel):
    answer: str
    tools_called: list[str]              # was: tool_called: str | None
    citations: list[Citation] | None = None
    legal_draft: LegalDraftResult | None = None
```

### Phase 2 — Signal wiring

**Files:** `services/api/src/api/manager_router.py`,
`apps/signal-bot/src/signal_bot/main.py`

- `POST /manager/ask` accepts `get_effective_user` as an alternate
  dependency, mirroring `/chat`'s existing pattern exactly (same
  `X-On-Behalf-Of-Phone` header mechanism, same 403-on-unlinked
  behavior) — this is the specific gap the router's own docstring
  already names.
- `signal_bot.ask_collabrains()` posts to `/manager/ask` instead of
  `/chat`, same auth headers.
- Signal is plain text — if a reply's `legal_draft.disclaimer` is
  present, prepend it to the message text before sending, so Signal
  users get the same compliance disclosure as web users instead of
  losing it to the medium.

### Phase 3 — Frontend consolidation

**Files:** `apps/web/src/routes/Chat.tsx` (kept, extended),
`apps/web/src/routes/Legal.tsx` / `Assistant.tsx` (deleted, with
their tests), `apps/web/src/lib/navigation.ts`, `apps/web/src/lib/api.ts`

- One route (`/chat`), one nav item (existing `nav.aiChat` label).
- `Chat.tsx`'s turn rendering gains: a disclaimer box when a turn's
  `legal_draft` field is set (reusing `Legal.tsx`'s existing
  disclaimer styling), and the "via: tools" line pluralized (joined
  tool names) instead of a single tool.
- `apps/web/src/lib/api.ts`: `chat()` and `legalDraft()` calls are
  removed; `askManager()` (or a renamed equivalent) becomes the only
  AI-interaction call, with its return type matching the new
  `AskResponse` shape.
- Once nothing calls them, `/chat` and `/legal/draft` FastAPI routers
  are deleted, not left as unused dead code.

**i18n cost, stated directly:** the `legal.instructionLabel`,
`legal.instructionPlaceholder`, `legal.scopeLabel` keys (and
similar `assistant.*` copy describing UI elements that won't exist
anymore) translated in ADR 0058 two rounds ago don't carry forward.
That work isn't wasted — the pages worked correctly in the meantime —
but it doesn't survive this consolidation unchanged.

### Phase 4 — Phone-at-creation + onboarding (independent of 1-3)

**Files:** `services/api/src/api/admin_router.py`,
`services/api/src/api/auth.py`, `services/api/src/api/models.py`,
new Alembic migration, `apps/web/src/routes/AdminDashboard.tsx`,
new onboarding component in `apps/web/src/`

- `AdminUserCreate` gains `phone_number: str | None = None`, validated
  by a shared E.164 validator extracted from `PUT /auth/me/phone`'s
  existing check (one rule, not duplicated).
- New table `pending_user_phone_numbers(username PK, phone_number,
  created_at)`. `admin_create_user` writes a row here when a phone
  was provided (the LDAP entry itself is unchanged — this stays a
  Postgres-only concern, consistent with `auth.py`'s own stated
  division: "LDAP is the identity source... Postgres is the
  authorization source").
- `_get_or_provision_user` (`auth.py`), when creating a brand-new
  `User` row, checks this table for the username, consumes (reads +
  deletes) a match if present, and sets `phone_number` on the new row.
- New `User.phone_prompt_dismissed: bool = False` column.
- New endpoint `PATCH /auth/me/dismiss-phone-prompt`, no request body,
  sets `phone_prompt_dismissed = True` on the caller and returns the
  updated `UserOut`, same response shape as `PUT /auth/me/phone`.
- Frontend: a one-time modal shown post-login when
  `phone_number is None and not phone_prompt_dismissed` — "Set phone
  number" (calls existing `PUT /auth/me/phone`) or "Skip" (calls the
  new dismiss endpoint). Users who already have a phone number, or
  who already dismissed the prompt, never see it.

## Testing

- **Phase 1**: existing Manager Agent tests extended for multi-round
  scenarios (2-3 chained tool calls, a round-cap-exceeded case, a
  mid-chain tool failure that the model recovers from). New unit
  tests for both new tools in isolation (grounding refusal, disclaimer
  always present in `draft_legal_document`'s result regardless of
  instruction phrasing).
- **Phase 2**: signal-bot's existing test suite gets an `/manager/ask`
  variant of its `/chat`-bridging tests; a real Signal round-trip
  (same throwaway-QA-session discipline used all session) including
  one message that triggers a tool call.
- **Phase 3**: `Chat.test.tsx` extended for the disclaimer-box and
  multi-tool "via:" rendering; `Legal.test.tsx`/`Assistant.test.tsx`
  deleted along with the routes they tested.
- **Phase 4**: a real create-user-with-phone → first-login round trip
  (matches the actual bug class this phase exists to prevent —
  asserting the staging table logic in isolation isn't enough,
  same lesson as every "verified via live testing, not just unit
  tests" finding logged elsewhere in this project's ADRs).

Each phase deploys and is verified independently, per this project's
established discipline (isolated scratch-dir + throwaway Docker
container test → live verification → ADR → commit direct to `main`),
not as one combined change.

## Open questions resolved during brainstorming

- Unification shape: **one page, no modes**, not three pages sharing
  a backend, not a mode-switching single page.
- Tool-call rounds: **multi-round**, capped at `MAX_TOOL_ROUNDS = 5`.
- Phone-at-creation mechanism: **staging table + skippable onboarding
  prompt**, not a hard onboarding gate, not LDAP-attribute staging.
