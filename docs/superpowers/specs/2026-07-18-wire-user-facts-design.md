# Wire UserFacts into chat and legal drafting — Design

## Status

Approved (brainstormed 2026-07-18)

## Context

The user reported "the AI agents don't work well and it doesn't remember
anything about the users." Investigation (this session, read the actual
code rather than assuming) found the concrete cause: `services/api/src/api/user_facts.py`
extracts durable, time-bound facts about a user (address, employer, etc.)
from ingested documents, with a full `pending_review` → `confirmed`/`rejected`
approval flow (`facts_router.py`) — but nothing ever reads a confirmed
fact back out. `chat.py`, `legal.py`, and `manager_agent.py` have zero
references to `UserFact` anywhere. The system extracts and stores facts,
an admin can review and approve them, and then they are never used again.

This sits alongside a working, separate system: `memory.py`'s episodic
`Memory` table (short-term conversational recall, retrieved by semantic
similarity, already wired into `chat.py`). `UserFact` is not a duplicate
of that — it answers "what is durably true about this person right now"
(structured, time-bound, admin-reviewed), which is a different question
than "what did we discuss before" (semantic, episodic, auto-created).

**Where the fix has leverage**: `chat.py`'s `answer_grounded_question` is
the one function behind both `POST /chat` and the Manager Agent's
`answer_from_documents` tool (`tools.py:_answer_from_documents_handler`
calls it directly). `legal.py`'s `_generate_draft` is the one function
behind both `POST /legal/draft` and the Manager Agent's
`draft_legal_document` tool (`tools.py:_draft_legal_document_handler`
calls it directly). Fixing these two shared functions reaches all four
AI-facing entry points with two call-site changes — no new endpoints,
no manager-agent tool schema changes.

## Goals

1. A user's currently-valid, admin-confirmed facts are visible to the
   model whenever it generates a chat answer or a legal draft — for that
   user, via `/chat`, `/legal/draft`, or either Manager Agent tool that
   wraps them.
2. Only `status == "confirmed"` facts are ever injected — an unreviewed
   `pending_review` extraction (which could be wrong; that's the entire
   reason the review step exists) must never reach a generated answer.
3. Facts retrieval failing must never fail the chat/draft response — same
   "quality feature, not a hard dependency" discipline every other
   optional context source in these two functions already follows
   (memory retrieval, preference lookup, reflection).

## Non-goals

- A standalone `search_facts`/`list_facts` Manager Agent tool for
  fact-only questions with no document-retrieval trigger (e.g. "what's
  my address?" when no document matches). The two shared-function fixes
  above already cover every case where the model is generating a
  grounded answer or draft; a fact-only query path is a materially
  different capability (new tool descriptor, new JSON schema, new
  permission scoping) and isn't needed to close the reported gap.
- Any change to the extraction pipeline (`extract_facts_from_document`)
  or the review UI/endpoints (`facts_router.py`) — both already work
  correctly; this pass only adds a read path for already-confirmed data.
- Any change to `memory.py`'s episodic-memory system — it already works
  and is out of scope; this pass adds a second, independent context
  source alongside it, not a replacement or merge.
- Injecting facts into the Manager Agent's other tools (`summarize_document`,
  `extract_tasks`, `search`) — none of them generate a user-facing
  narrative answer the way `answer_from_documents`/`draft_legal_document`
  do, so a "known facts" block wouldn't change their behavior.

## Design

### `services/api/src/api/user_facts.py` — new function

```python
async def get_current_facts(db: AsyncSession, *, user_id: UUID) -> list[UserFact]:
    """Confirmed facts valid right now (Phase 26 read path -- extraction
    and review already existed; nothing consumed the result until this).
    Only status == "confirmed": a pending_review fact could be a bad
    extraction, which is exactly what the review step exists to catch."""
    today = date.today()
    result = await db.execute(
        select(UserFact)
        .where(
            UserFact.user_id == user_id,
            UserFact.status == "confirmed",
            UserFact.valid_from <= today,
            or_(UserFact.valid_to.is_(None), UserFact.valid_to >= today),
        )
        .order_by(UserFact.fact_type)
    )
    return list(result.scalars().all())
```

(`or_` already imported in this module; `date` already imported.)

### `services/api/src/api/chat.py`

`answer_grounded_question` gains a facts-retrieval step alongside the
existing memory-retrieval step (same try/except-never-fail shape):

```python
    try:
        facts = await get_current_facts(db, user_id=user_id)
    except Exception:  # noqa: BLE001 - facts retrieval must never fail the answer
        logger.exception("facts retrieval failed for grounded question")
        facts = []

    facts_text = ""
    if facts:
        fact_lines = "\n".join(f"- {fact.fact_type}: {fact.value.get('text', '')}" for fact in facts)
        facts_text = f"\n\nKnown facts about the user:\n{fact_lines}"
```

`_build_messages` gains a `facts_text` parameter (same shape as the
existing `memory_text` one) and folds it into the same content string —
currently:

```python
    messages.append({"role": "user", "content": f"Context:\n{context_text}{memory_text}\n\nQuestion: {question}"})
```

becomes:

```python
    messages.append({"role": "user", "content": f"Context:\n{context_text}{facts_text}{memory_text}\n\nQuestion: {question}"})
```

Both call sites of `_build_messages` inside `answer_grounded_question`
(the initial call and the reflection-triggered retry) pass `facts_text`
— fetched once, reused across the retry exactly like `memory_text` and
`language_instruction` already are (facts aren't retrieval-scope-dependent
the way document chunks are, so there's nothing to refresh on retry).

### `services/api/src/api/legal.py`

`_generate_draft` currently has no memory/facts awareness at all — this
is the first context source beyond retrieved documents. Add the same
retrieval step, and fold `facts_text` into both of the function's two
`messages` constructions (initial and reflection-retry) — currently:

```python
        {"role": "user", "content": f"Context:\n{context_text}\n\nDrafting instruction: {instruction}"},
```

becomes:

```python
        {"role": "user", "content": f"Context:\n{context_text}{facts_text}\n\nDrafting instruction: {instruction}"},
```

## Testing

- `test_user_facts.py` gains direct tests for `get_current_facts`:
  returns a confirmed fact valid today; excludes a `pending_review` fact;
  excludes a fact whose `valid_to` has passed; excludes a fact whose
  `valid_from` is in the future; excludes a `rejected` fact.
- `test_chat.py` gains an HTTP-level test following the existing
  `test_chat_includes_preferred_language_in_system_prompt` pattern
  (mock `chat_completion`, inspect `mock_completion.call_args.args[0]`
  for the injected fact text) — confirms a confirmed fact appears in the
  sent messages, and a separate test confirms a `pending_review` fact
  does not.
- `test_legal.py` gains the equivalent test for `/legal/draft`.
- Full suite (`pytest`) green, matching this session's established
  baseline-vs-pre-existing-failure discipline (the ~28 known pre-existing
  test-DB-pollution failures documented earlier today are unrelated and
  expected to remain).

## Open questions resolved during brainstorming

- **Which facts count as "current"**: `status == "confirmed"` AND
  `valid_from <= today` AND (`valid_to` is null OR `valid_to >= today`)
  — mirrors `facts_router.py`'s existing `as_of` filter, restricted to
  confirmed-only since that endpoint's `list_facts` intentionally returns
  all statuses (it's the review UI's data source) while this read path
  is answer-generation-facing and must never surface an unreviewed guess.
- **Where to inject facts in the prompt**: as a distinct labeled block
  ("Known facts about the user:"), same pattern as the existing "Relevant
  memories:" block in `chat.py` — not merged into the document `Context:`
  block, since facts aren't retrieved document content and conflating
  them would make citation markers ambiguous.
- **Manager Agent tool coverage**: no new tool needed — both tools that
  generate narrative answers (`answer_from_documents`, `draft_legal_document`)
  already call the two functions this design fixes.
