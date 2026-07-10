# 0059 — Manager Agent: multi-round tool-calling and terminal tools

## Status

Accepted

## Context

Phase 1 of the unified-chat-consolidation design
(`docs/superpowers/specs/2026-07-10-unified-chat-consolidation-design.md`)
covers backend changes to the Manager Agent (Phase 11, ADR 0026),
landed as a sequence of five small changes:

1. Extracted `/chat`'s pipeline (retrieve, memory, generate,
   Reflection retry, background memory extraction) out of the route
   handler into a standalone `answer_grounded_question()` in
   `api/chat.py`, returning a `GroundedAnswer {answer, citations}`.
   `/chat` itself is now a thin wrapper around it.
2. Registered a new `answer_from_documents` tool in `api/tools.py`
   wrapping that function, so the Manager Agent can offer the same
   grounded, Reflection-checked, memory-aware document Q&A that `/chat`
   always had — previously only reachable outside the tool-calling
   flow.
3. Changed `handle_request()`'s return shape from a nullable single
   `tool_called: str | None` to `tools_called: list[str]`, since a
   request can now involve more than one tool call.
4. Replaced the old "dispatch at most one tool, then always make one
   more `chat_completion()` call to synthesize a final answer" flow
   with a bounded loop (`MAX_TOOL_ROUNDS = 5`): every round offers
   tools again via `chat_completion_with_tools`, so the model can chain
   several tool calls to satisfy a compound request (e.g. "look up
   this plate, then draft a letter to the owner").
5. This change: make `answer_from_documents` and `draft_legal_document`
   *terminal* — dispatching either ends the loop immediately with that
   tool's own result, instead of spending another model round
   re-synthesizing an answer that was already finished.

This ADR covers change 5, the last of the five and the one that closes
out the backend half of the design doc's Phase 1.

## Decision

### `answer_from_documents` is a new tool, not a change to `search`

`search` already existed (Phase 9a, ADR 0021) and returns raw
hybrid-search hits for the model to reason over further — useful when
the model wants intermediate context, e.g. as one step of a longer
chain. `answer_from_documents` returns a *finished* answer: it runs
through Reflection (ADR 0020, checks the answer is actually supported
by context and retries retrieval once if not) and long-term memory
(ADR 0018, retrieves and reinforces relevant past-conversation
memories) — a fully independent pipeline `search`'s raw hits never
went through. Folding that behavior into `search` would mean every
caller of `search` (including chains that genuinely want raw chunks)
pays for Reflection and memory unconditionally, and would collapse two
different response shapes (raw hits vs. a grounded answer with
citations) into one tool with conditional behavior. Keeping them
separate tools lets the model pick the right one for the request, and
keeps each tool's contract simple: `search` returns hits, unconditionally, whereas `answer_from_documents` returns a
finished answer.

### Why these two tools are terminal and the rest aren't

`answer_from_documents` and `draft_legal_document` are the only two
registered tools whose result is *already a finished response*, not
data for the model to reason over:

- `answer_from_documents`'s result already passed Reflection — a
  quality check that the answer is actually supported by retrieved
  context. Feeding it back through another `chat_completion()` round
  to "synthesize a final answer" would let the model paraphrase or
  restate an answer that was already correct and already
  fact-checked, at the cost of an extra generation (23-85s per this
  host's own load-testing, ADR 0015) for no quality benefit, and with
  a real risk of the restatement drifting from what Reflection
  actually verified.
- `draft_legal_document`'s result is a complete draft with citations
  and a `disclaimer` field. The disclaimer is a data-shape guarantee
  threaded straight through to the API response, not prose the model
  is trusted to remember to include in a follow-up synthesis. Routing
  it through another round risks the model dropping or paraphrasing
  the disclaimer.

Every other tool (`search`, `summarize_document`, `extract_tasks`,
`extract_entities`, `lookup_vehicle`) stays informational: its result
feeds back into the loop as a `tool` message, and the model decides
whether to call another tool or produce a final answer. This is what
makes compound chains work, e.g. `lookup_vehicle` → `draft_legal_document`
("look up this plate, then draft a letter to the owner") — the vehicle
lookup result feeds the next round's context, and drafting is the
chain's terminal step.

### Response shape

`handle_request()` gains two new optional keys, populated only by the
two terminal tools and `None` otherwise:

```python
{
    "answer": str,
    "tools_called": list[str],
    "citations": list[Citation] | None,     # set by answer_from_documents
    "legal_draft": DraftResponse | None,    # set by draft_legal_document
}
```

`AskResponse` (`manager_router.py`) gains matching optional fields.
This is purely additive — existing callers reading only `answer` and
`tools_called` are unaffected. `apps/web` is not touched by this
change (frontend consolidation is Phase 3 of the design doc, a
separate follow-on plan); its `AskResponse` TypeScript interface will
simply be missing these two fields until that phase, with no breaking
effect on current behavior.

### Error handling within the loop

A failed dispatch (`KeyError`/`ValueError`/`ToolPermissionError`) never
produces a `result` dict, so it can't be a candidate for the
terminal-tool check — the except branch now `continue`s straight to
the next loop iteration after recording the tool name and feeding an
`{"error": ...}` tool-result back to the model, rather than falling
through into logic that assumes `result` exists.

## Consequences

- Compound requests that end in a grounded answer or a legal draft no
  longer pay for an extra, unnecessary generation round, and can't
  have the terminal tool's disclaimer or citations silently dropped or
  reworded by a subsequent synthesis step.
- Adding a third terminal tool in the future means adding its name to
  `TERMINAL_TOOLS` and one more `if` branch in the loop's dispatch
  handling — the mechanism generalizes past two tools if needed.
- Signal wiring (Phase 2) and frontend consolidation (Phase 3) of the
  design doc remain separate, not-yet-started follow-on plans; this
  ADR only covers the backend (`services/api`) changes.

## Verification

Unit tests (`services/api/tests/test_manager_agent.py`,
`test_manager_router.py`) cover: `answer_from_documents` and
`draft_legal_document` each short-circuit the loop after exactly one
`chat_completion_with_tools` call, returning that tool's own
answer/citations or draft/disclaimer; a non-terminal tool (`search`)
still requires a second round-trip to produce a final answer; the two
earlier return paths (no permitted tools, no tool requested) and the
round-cap-exceeded fallback all include the two new keys (`None`) for
a consistent response shape across every return path.

This sandbox has no local Docker/Postgres, so these tests were
verified by `python -m py_compile` (syntax) plus a manual trace of
each test against the implementation, matching mocks to call sites
line by line, rather than by running `pytest` against a live database
in this environment. A consolidated live-DB verification (deploy to
the throwaway Docker container, run the full suite there, then a real
`/manager/ask` Playwright/QA check exercising both terminal tools) is
planned as a single pass covering all five tasks of this plan, at the
end of the whole project, rather than one live-verification round per
task.
