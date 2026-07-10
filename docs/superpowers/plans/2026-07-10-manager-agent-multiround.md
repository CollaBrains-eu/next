# Manager Agent Multi-Round + Grounded/Legal Terminal Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Manager Agent (`/manager/ask`) capable of chaining several tool calls per request, and able to produce a fully grounded, Reflection-checked, memory-aware document answer or a disclaimer-bearing legal draft as a *finished* response — the two pieces of behavior needed before Signal and the frontend can be pointed at this single endpoint (later plans).

**Architecture:** `manager_agent.handle_request()` changes from "one tool call, then one final synthesis call" to a bounded loop (`MAX_TOOL_ROUNDS = 5`) that keeps dispatching tools and feeding results back until the model stops requesting them. Two tool names are treated as **terminal**: `answer_from_documents` (new — wraps `chat.py`'s real pipeline: retrieve → generate → Reflection → memory) and `draft_legal_document` (existing). Dispatching either ends the loop immediately with that tool's own result as the final answer, instead of running another model round to re-synthesize an already-finished, already-grounded answer.

**Tech Stack:** FastAPI, SQLAlchemy async, Ollama native function-calling (existing `api.ai_gateway.chat_completion_with_tools`), pytest + pytest-asyncio (existing test harness, `client` fixture).

## Global Constraints

- `MAX_TOOL_ROUNDS = 5` — from `docs/superpowers/specs/2026-07-10-unified-chat-consolidation-design.md`.
- No change to per-round tool error handling: a failed dispatch (`KeyError`/`ValueError`/`ToolPermissionError`) becomes an `{"error": ...}` tool-result message fed back to the model — this already exists in `handle_request()`, the loop just repeats it per round.
- `answer_grounded_question()` (the extracted pipeline) must live inside `services/api/src/api/chat.py`, not a new module — existing tests patch `api.chat.hybrid_search`, `api.chat.chat_completion`, `api.chat.reflect` by that module path, and `unittest.mock.patch` patches where a name is *looked up*, not where it's defined. Moving the logic elsewhere would silently break every existing `test_chat.py` mock.
- Every task in this plan must leave `pytest services/api/tests/ -x` fully green before its commit step — this plan does not get to break existing tests "temporarily."

---

### Task 1: Extract `chat.py`'s pipeline into a reusable function

**Files:**
- Modify: `services/api/src/api/chat.py`
- Test: `services/api/tests/test_chat.py` (no changes — this task's test is "all existing tests still pass unchanged")

**Interfaces:**
- Produces: `class GroundedAnswer(BaseModel): answer: str; citations: list[Citation]` and `async def answer_grounded_question(db: AsyncSession, *, user_id: UUID, message: str, history: list[ChatTurn] | None = None, context_chunks: int = 5) -> GroundedAnswer`, both in `api.chat`. Later tasks (Task 2) import this function.

This is a pure refactor: every line of behavior in the current `chat()` route handler moves into a new function, and the route becomes a thin wrapper. No behavior changes, which is exactly what makes "all existing tests still pass" a valid verification.

- [ ] **Step 1: Read the current route handler to confirm the exact code being moved**

Run: `sed -n '104,178p' services/api/src/api/chat.py`

This is the `_build_messages` helper (already extracted) plus the full `chat()` route body — confirm nothing has changed since this plan was written before proceeding.

- [ ] **Step 2: Replace the route handler with the extracted function + a thin wrapper**

In `services/api/src/api/chat.py`, replace everything from `class ChatResponse` through the end of the `chat()` function with:

```python
class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]


class GroundedAnswer(BaseModel):
    answer: str
    citations: list[Citation]


async def _retrieve(db: AsyncSession, query: str, limit: int) -> tuple[list[Citation], str]:
    hits = await hybrid_search(db, query, limit=limit)

    citations: list[Citation] = []
    context_blocks: list[str] = []
    if hits:
        document_ids = {hit.chunk.document_id for hit in hits}
        documents_result = await db.execute(select(Document).where(Document.id.in_(document_ids)))
        titles = {doc.id: doc.title for doc in documents_result.scalars().all()}

        for marker, hit in enumerate(hits, start=1):
            citations.append(
                Citation(
                    marker=marker,
                    document_id=hit.chunk.document_id,
                    document_title=titles.get(hit.chunk.document_id, ""),
                    chunk_id=hit.chunk.id,
                )
            )
            context_blocks.append(f"[{marker}] {hit.chunk.content}")

    context_text = "\n\n".join(context_blocks) if context_blocks else "(no relevant documents found)"
    return citations, context_text


async def _extract_and_store_memory(user_id: UUID, user_message: str, answer: str) -> None:
    try:
        async with async_session() as db:
            await maybe_create_memory_from_exchange(db, user_id=user_id, user_message=user_message, answer=answer)
    except Exception:  # noqa: BLE001 - background memory extraction must never surface as a request failure
        logger.exception("memory extraction failed for user %s", user_id)


def _build_messages(
    history: list[ChatTurn], context_text: str, question: str, memory_text: str = "",
    language_instruction: str = "",
) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT + language_instruction}]
    messages.extend({"role": turn.role, "content": turn.content} for turn in history)
    messages.append({"role": "user", "content": f"Context:\n{context_text}{memory_text}\n\nQuestion: {question}"})
    return messages


async def answer_grounded_question(
    db: AsyncSession, *, user_id: UUID, message: str,
    history: list[ChatTurn] | None = None, context_chunks: int = 5,
) -> GroundedAnswer:
    """The full /chat pipeline (retrieve, memory, generate, Reflection, retry,
    background memory extraction) as a reusable function -- both the /chat
    route and api.tools' answer_from_documents tool call this, so document
    Q&A keeps Reflection and long-term memory no matter which caller reaches it.

    Runs outside a request lifecycle for tool-handler callers (no
    BackgroundTasks available), so the background memory-extraction step
    uses asyncio.create_task directly instead -- same fire-and-forget
    semantics as the route's background_tasks.add_task call.
    """
    history = history or []
    citations, context_text = await _retrieve(db, message, context_chunks)

    try:
        memories = await retrieve_relevant_memories(db, user_id=user_id, query=message)
    except Exception:  # noqa: BLE001 - memory retrieval must never fail the answer
        logger.exception("memory retrieval failed for grounded question")
        memories = []

    memory_text = ""
    if memories:
        memory_lines = "\n".join(f"- {memory.summary}" for memory in memories)
        memory_text = f"\n\nRelevant memories:\n{memory_lines}"

    language_instruction = ""
    try:
        preferences = await get_preferences(db, user_id=user_id)
        language_instruction = build_language_instruction(preferences.preferred_language if preferences else None)
    except Exception:  # noqa: BLE001 - preference lookup must never fail the answer
        logger.exception("preference lookup failed for grounded question")

    messages = _build_messages(history, context_text, message, memory_text, language_instruction)
    answer = await chat_completion(messages, user_id=user_id, endpoint="chat")

    try:
        result = await reflect(question=message, answer=answer, context_text=context_text, user_id=user_id, endpoint="chat")
        retried = False
        if not result.sufficient_evidence and context_chunks < REFLECTION_RETRY_CAP:
            retry_limit = min(context_chunks * 2, REFLECTION_RETRY_CAP)
            citations, context_text = await _retrieve(db, message, retry_limit)
            messages = _build_messages(history, context_text, message, memory_text, language_instruction)
            answer = await chat_completion(messages, user_id=user_id, endpoint="chat")
            retried = True
        await log_reflection(db, user_id=user_id, endpoint="chat", question=message, result=result, retried=retried)
        if result.sufficient_evidence and memories:
            await reinforce_memories(db, [memory.id for memory in memories])
    except Exception:  # noqa: BLE001 - reflection is a quality check, must never fail the answer
        logger.exception("reflection failed for grounded question from user %s", user_id)

    asyncio.create_task(_extract_and_store_memory(user_id, message, answer))

    return GroundedAnswer(answer=answer, citations=citations)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    background_tasks: BackgroundTasks,
    request: ChatRequest,
    context_chunks: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> ChatResponse:
    result = await answer_grounded_question(
        db, user_id=current_user.id, message=request.message,
        history=request.history, context_chunks=context_chunks,
    )
    return ChatResponse(answer=result.answer, citations=result.citations)
```

Add `import asyncio` to the top of `services/api/src/api/chat.py` alongside the existing imports (it currently has no `asyncio` import).

Note `background_tasks: BackgroundTasks` stays a parameter of the route (FastAPI needs it declared to inject it) even though it's now unused inside the route body — remove the `background_tasks` parameter entirely instead, since nothing references it anymore:

```python
@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    context_chunks: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> ChatResponse:
    result = await answer_grounded_question(
        db, user_id=current_user.id, message=request.message,
        history=request.history, context_chunks=context_chunks,
    )
    return ChatResponse(answer=result.answer, citations=result.citations)
```

Also remove the now-unused `from fastapi import APIRouter, BackgroundTasks, Depends, Query` → `from fastapi import APIRouter, Depends, Query` (drop `BackgroundTasks`).

- [ ] **Step 3: Run the full existing chat test suite**

Run: `cd services/api && python -m pytest tests/test_chat.py -v`
Expected: all 10 existing tests PASS, unchanged. If any fail, the extraction changed behavior — stop and compare against the original route body from Step 1 line by line rather than patching the test.

- [ ] **Step 4: Run the full backend suite to check for ripple effects**

Run: `cd services/api && python -m pytest tests/ -x`
Expected: PASS (same count as before this task started).

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/chat.py
git commit -m "refactor: extract /chat's pipeline into answer_grounded_question()

Pure extraction, no behavior change -- the route becomes a thin
wrapper. Sets up api.tools.answer_from_documents (next task) to reuse
the same Reflection- and memory-aware pipeline instead of a raw
hybrid_search call that would silently drop both."
```

---

### Task 2: Add the `answer_from_documents` tool

**Files:**
- Modify: `services/api/src/api/tools.py`
- Test: `services/api/tests/test_tools.py`

**Interfaces:**
- Consumes: `api.chat.answer_grounded_question(db, *, user_id, message, history=None, context_chunks=5) -> GroundedAnswer` (Task 1).
- Produces: a registered tool named `answer_from_documents`, dispatchable via `api.tool_registry.dispatch("answer_from_documents", db=db, user_id=..., message=...)` returning `{"answer": str, "citations": list[dict]}`. Task 3 checks for this exact tool name to apply terminal-tool handling.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_tools.py`:

```python
async def test_answer_from_documents_tool_returns_grounded_answer():
    from api.chat import Citation, GroundedAnswer

    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    fake_answer = GroundedAnswer(
        answer="the answer",
        citations=[Citation(marker=1, document_id=uuid4(), document_title="t", chunk_id=uuid4())],
    )

    async with async_session() as db:
        with patch("api.tools.answer_grounded_question", return_value=fake_answer):
            result = await dispatch("answer_from_documents", db=db, user_id=user.id, message="what is x")

    assert result["answer"] == "the answer"
    assert result["citations"][0]["document_title"] == "t"


async def test_answer_from_documents_tool_passes_history_through():
    from api.chat import GroundedAnswer

    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    fake_answer = GroundedAnswer(answer="ok", citations=[])

    async with async_session() as db:
        with patch("api.tools.answer_grounded_question", return_value=fake_answer) as mock_answer:
            await dispatch(
                "answer_from_documents", db=db, user_id=user.id, message="follow-up",
                history=[{"role": "user", "content": "earlier question"}],
            )

    assert mock_answer.call_args.kwargs["history"] == [{"role": "user", "content": "earlier question"}]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/api && python -m pytest tests/test_tools.py -k answer_from_documents -v`
Expected: FAIL with `KeyError: 'unknown tool: 'answer_from_documents''` (the tool isn't registered yet).

- [ ] **Step 3: Implement the tool**

In `services/api/src/api/tools.py`, add `answer_grounded_question` to the import from `api.chat`:

```python
from api.chat import answer_grounded_question
```

Add the handler (place it after `_search_handler`, before `_summarize_document_handler`):

```python
async def _answer_from_documents_handler(
    *, db: AsyncSession, user_id: UUID, message: str, history: list[dict] | None = None,
) -> dict[str, Any]:
    result = await answer_grounded_question(db, user_id=user_id, message=message, history=history)
    return result.model_dump(mode="json")
```

Register it (place after the `search` registration, since it's the same domain):

```python
register_tool(ToolDescriptor(
    name="answer_from_documents",
    description=(
        "Answer a question using only the content of indexed documents, with "
        "citations. Use this for any question that should be answered from the "
        "user's documents -- it retrieves, grounds, and fact-checks its own "
        "answer before returning it. Prefer this over 'search' when the goal is "
        "a finished answer rather than raw search results to reason over further."
    ),
    permissions=["documents.read"],
    input_schema={
        "message": "string",
        "history": "array of {role, content} (optional, prior conversation turns)",
    },
    output_schema={"answer": "string", "citations": "array of {marker, document_id, document_title, chunk_id}"},
    handler=_answer_from_documents_handler,
))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd services/api && python -m pytest tests/test_tools.py -k answer_from_documents -v`
Expected: PASS.

- [ ] **Step 5: Run the full backend suite**

Run: `cd services/api && python -m pytest tests/ -x`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/tools.py services/api/tests/test_tools.py
git commit -m "feat: register answer_from_documents tool wrapping the Reflection/memory-aware chat pipeline"
```

---

### Task 3: Change the Manager Agent's response shape to `tools_called: list[str]`

**Files:**
- Modify: `services/api/src/api/manager_agent.py`, `services/api/src/api/manager_router.py`
- Test: `services/api/tests/test_manager_agent.py`, `services/api/tests/test_manager_router.py`

**Interfaces:**
- Produces: `handle_request()` returns `{"answer": str, "tools_called": list[str]}` (was `{"answer": str, "tool_called": str | None}`). `AskResponse.tools_called: list[str]` (was `tool_called: str | None`).

This task isolates the response-shape change from the multi-round loop itself (Task 4) so each is independently reviewable — still exactly one tool dispatched per request after this task, just reported as a one-item (or empty) list instead of a nullable string.

- [ ] **Step 1: Update the existing tests to the new shape**

In `services/api/tests/test_manager_agent.py`, change every occurrence of the old shape. Use individual-key assertions (`result["answer"] == ...` / `result["tools_called"] == ...`) rather than full-dict equality — Task 5 adds two more keys (`citations`, `legal_draft`) to every return path, and individual-key assertions stay valid across that change without needing to be revisited, unlike `result == {...}` which would break the moment the dict grows:

```python
# test_handle_request_with_no_permitted_tools_falls_back_to_plain_completion
assert result["answer"] == "a direct answer"
assert result["tools_called"] == []

# test_handle_request_returns_direct_answer_when_model_requests_no_tool
assert result["answer"] == "just an answer"
assert result["tools_called"] == []

# test_handle_request_dispatches_a_real_tool_end_to_end
assert result["answer"] == "Here's what I found."
assert result["tools_called"] == ["search"]

# test_handle_request_feeds_a_tool_error_back_to_the_model
assert result["answer"] == "I couldn't find that document."
assert result["tools_called"] == ["summarize_document"]

# test_handle_request_denies_a_tool_the_role_lacks_permission_for
assert result["tools_called"] == ["search"]
```

In `services/api/tests/test_manager_router.py`:

```python
# test_ask_returns_a_direct_answer_when_no_tool_is_needed
assert body["tools_called"] == []

# test_ask_dispatches_a_tool_end_to_end
assert body["tools_called"] == ["search"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/api && python -m pytest tests/test_manager_agent.py tests/test_manager_router.py -v`
Expected: FAIL — the code still returns `tool_called`, not `tools_called`.

- [ ] **Step 3: Update `handle_request()`'s return shape**

In `services/api/src/api/manager_agent.py`, change both `return` statements that currently use `"tool_called"`:

```python
    tools = _tools_for_role(role)
    if not tools:
        answer = await chat_completion(messages, user_id=user_id, endpoint="manager_agent")
        return {"answer": answer, "tools_called": []}

    response_message = await chat_completion_with_tools(
        messages, user_id=user_id, endpoint="manager_agent", tools=tools,
    )
    tool_calls = response_message.get("tool_calls")
    if not tool_calls:
        return {"answer": response_message.get("content", ""), "tools_called": []}

    call = tool_calls[0]
    function = call.get("function", {})
    tool_name = function.get("name")
    arguments = function.get("arguments") or {}

    try:
        result = await dispatch(tool_name, db=db, user_id=user_id, **arguments)
        result_content = json.dumps(result)
    except (KeyError, ValueError, ToolPermissionError) as exc:
        result_content = json.dumps({"error": str(exc)})
        logger.info("manager agent tool call %r failed: %s", tool_name, exc)

    follow_up_messages = [
        *messages,
        {"role": "assistant", "content": "", "tool_calls": tool_calls},
        {"role": "tool", "content": result_content},
    ]
    answer = await chat_completion(follow_up_messages, user_id=user_id, endpoint="manager_agent")

    return {"answer": answer, "tools_called": [tool_name]}
```

- [ ] **Step 4: Update `AskResponse`**

In `services/api/src/api/manager_router.py`:

```python
class AskResponse(BaseModel):
    answer: str
    tools_called: list[str]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd services/api && python -m pytest tests/test_manager_agent.py tests/test_manager_router.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `cd services/api && python -m pytest tests/ -x`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/api/src/api/manager_agent.py services/api/src/api/manager_router.py services/api/tests/test_manager_agent.py services/api/tests/test_manager_router.py
git commit -m "refactor: manager agent reports tools_called as a list instead of a nullable string

Prep for multi-round tool calling (next task) -- one request can soon
dispatch more than one tool, so the response needs to report all of
them, not just the last one."
```

---

### Task 4: Multi-round tool-calling loop

**Files:**
- Modify: `services/api/src/api/manager_agent.py`
- Test: `services/api/tests/test_manager_agent.py`

**Interfaces:**
- Consumes: `MAX_TOOL_ROUNDS = 5` (Global Constraints).
- Produces: `handle_request()` can now report `tools_called` with more than one entry.

- [ ] **Step 1: Write the failing tests, and fix four existing tests whose mocks assume single-round behavior**

The loop means every round — including the one right after a tool
dispatch — calls `chat_completion_with_tools` again (offering tools
again, in case the model wants to chain another), not the plain
`chat_completion()` the old single-round code used for its one
post-dispatch synthesis call. Four existing tests mock
`chat_completion_with_tools` with a fixed `return_value` (not
`side_effect`) while expecting exactly one tool dispatch — under the
loop, a fixed `return_value` means *every* round gets the same
tool-call response, so the loop would dispatch that tool five times
(exhausting `MAX_TOOL_ROUNDS`) instead of once. Fix these first, in
`services/api/tests/test_manager_agent.py`:

```python
# Replace test_handle_request_dispatches_a_real_tool_end_to_end entirely:
async def test_handle_request_dispatches_a_real_tool_end_to_end():
    user = await _create_user(_unique("manageruser"))

    class _FakeChunk:
        def __init__(self):
            self.id = uuid4()
            self.document_id = uuid4()
            self.content = "found this"

    fake_hit = SearchHit(chunk=_FakeChunk(), score=0.7)
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hello"}}}],
    }
    final_response = {"content": "Here's what I found."}

    async with async_session() as db:
        with (
            patch(
                "api.manager_agent.chat_completion_with_tools",
                side_effect=[tool_call_response, final_response],
            ) as mock_with_tools,
            patch("api.tools.hybrid_search", return_value=[fake_hit]),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="find hello")

    assert result["answer"] == "Here's what I found."
    assert result["tools_called"] == ["search"]
    second_round_messages = mock_with_tools.call_args_list[1].args[0]
    assert second_round_messages[-1]["role"] == "tool"
    assert "found this" in second_round_messages[-1]["content"]


# Replace test_handle_request_feeds_a_tool_error_back_to_the_model entirely:
async def test_handle_request_feeds_a_tool_error_back_to_the_model():
    user = await _create_user(_unique("manageruser"))
    tool_call_response = {
        "content": "",
        "tool_calls": [{"function": {"name": "summarize_document", "arguments": {"document_id": str(uuid4())}}}],
    }
    final_response = {"content": "I couldn't find that document."}

    async with async_session() as db:
        with patch(
            "api.manager_agent.chat_completion_with_tools",
            side_effect=[tool_call_response, final_response],
        ) as mock_with_tools:
            result = await handle_request(db, user_id=user.id, role="member", message="summarize doc x")

    assert result["answer"] == "I couldn't find that document."
    assert result["tools_called"] == ["summarize_document"]
    second_round_messages = mock_with_tools.call_args_list[1].args[0]
    assert "error" in second_round_messages[-1]["content"]


# Replace test_handle_request_denies_a_tool_the_role_lacks_permission_for entirely:
async def test_handle_request_denies_a_tool_the_role_lacks_permission_for():
    # Simulates the model somehow requesting a tool outside its offered set
    # (a buggy/adversarial response) -- dispatch()'s own permission check
    # (ADR 0023) is the real backstop, not _tools_for_role's filtering alone.
    user = await _create_user(_unique("manageruser"), role="service")
    fake_tools = [{"type": "function", "function": {"name": "search", "description": "d", "parameters": {}}}]
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hello"}}}],
    }
    final_response = {"content": "Sorry, I can't do that."}

    async with async_session() as db:
        with (
            patch("api.manager_agent._tools_for_role", return_value=fake_tools),
            patch(
                "api.manager_agent.chat_completion_with_tools",
                side_effect=[tool_call_response, final_response],
            ) as mock_with_tools,
        ):
            result = await handle_request(db, user_id=user.id, role="service", message="find hello")

    assert result["tools_called"] == ["search"]
    second_round_messages = mock_with_tools.call_args_list[1].args[0]
    assert "error" in second_round_messages[-1]["content"]
```

And in `services/api/tests/test_manager_router.py`:

```python
# Replace test_ask_dispatches_a_tool_end_to_end entirely:
async def test_ask_dispatches_a_tool_end_to_end(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    class _FakeChunk:
        def __init__(self):
            self.id = uuid4()
            self.document_id = uuid4()
            self.content = "router result"

    fake_hit = SearchHit(chunk=_FakeChunk(), score=0.5)
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hello"}}}],
    }
    final_response = {"content": "Found it."}

    with (
        patch(
            "api.manager_agent.chat_completion_with_tools",
            side_effect=[tool_call_response, final_response],
        ),
        patch("api.tools.hybrid_search", return_value=[fake_hit]),
    ):
        response = await client.post("/manager/ask", headers=headers, json={"message": "find hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Found it."
    assert body["tools_called"] == ["search"]
```

Now add the three genuinely new tests, to `services/api/tests/test_manager_agent.py`:

```python
async def test_handle_request_chains_two_tool_calls():
    user = await _create_user(_unique("manageruser"))
    first_call = {
        "content": "", "tool_calls": [{"function": {"name": "lookup_vehicle", "arguments": {"kenteken": "AB-12-CD"}}}],
    }
    second_call = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "owner"}}}],
    }
    final = {"content": "Here's the combined answer."}

    async with async_session() as db:
        with (
            patch(
                "api.manager_agent.chat_completion_with_tools",
                side_effect=[first_call, second_call, final],
            ),
            patch("api.tools._lookup_vehicle", return_value=None),
            patch("api.tools.hybrid_search", return_value=[]),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="look up then search")

    assert result["answer"] == "Here's the combined answer."
    assert result["tools_called"] == ["lookup_vehicle", "search"]


async def test_handle_request_stops_at_max_rounds_without_a_final_answer():
    user = await _create_user(_unique("manageruser"))
    always_calls_search = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "x"}}}],
    }

    async with async_session() as db:
        with (
            patch("api.manager_agent.chat_completion_with_tools", return_value=always_calls_search),
            patch("api.tools.hybrid_search", return_value=[]),
            # MAX_TOOL_ROUNDS is exhausted without the model ever returning a
            # tool_calls-less response, so the loop falls through to one plain
            # chat_completion() call (not chat_completion_with_tools) to produce
            # a final answer -- this must be mocked separately or the test would
            # hit real Ollama.
            patch("api.manager_agent.chat_completion", return_value="ran out of steps") as mock_final,
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="loop forever")

    assert result["answer"] == "ran out of steps"
    assert result["tools_called"] == ["search"] * 5
    mock_final.assert_called_once()


async def test_handle_request_recovers_from_a_mid_chain_tool_error():
    user = await _create_user(_unique("manageruser"))
    failing_call = {
        "content": "", "tool_calls": [{"function": {"name": "summarize_document", "arguments": {"document_id": str(uuid4())}}}],
    }
    recovery_call = {"content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "x"}}}]}
    final = {"content": "Found it a different way."}

    async with async_session() as db:
        with (
            patch(
                "api.manager_agent.chat_completion_with_tools",
                side_effect=[failing_call, recovery_call, final],
            ),
            patch("api.tools.hybrid_search", return_value=[]),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="try then recover")

    assert result["answer"] == "Found it a different way."
    assert result["tools_called"] == ["summarize_document", "search"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/api && python -m pytest tests/test_manager_agent.py -k "chains_two_tool_calls or stops_at_max_rounds or recovers_from_a_mid_chain" -v`
Expected: FAIL — `handle_request()` still stops after one round (`chat_completion_with_tools` gets called only once, so `side_effect` list mismatches or the loop tests time out waiting for a second call that never happens).

- [ ] **Step 3: Implement the loop**

Replace `handle_request()` in `services/api/src/api/manager_agent.py` with:

```python
MAX_TOOL_ROUNDS = 5


async def handle_request(db: AsyncSession, *, user_id: UUID, role: str, message: str) -> dict[str, Any]:
    """Answer a free-form request, autonomously chaining up to MAX_TOOL_ROUNDS tool calls."""
    language_instruction = ""
    try:
        preferences = await get_preferences(db, user_id=user_id)
        language_instruction = build_language_instruction(preferences.preferred_language if preferences else None)
    except Exception:  # noqa: BLE001 - preference lookup must never fail the manager agent response
        logger.exception("preference lookup failed for manager agent request")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + language_instruction},
        {"role": "user", "content": message},
    ]

    tools = _tools_for_role(role)
    if not tools:
        answer = await chat_completion(messages, user_id=user_id, endpoint="manager_agent")
        return {"answer": answer, "tools_called": []}

    tools_called: list[str] = []
    for _round in range(MAX_TOOL_ROUNDS):
        response_message = await chat_completion_with_tools(
            messages, user_id=user_id, endpoint="manager_agent", tools=tools,
        )
        tool_calls = response_message.get("tool_calls")
        if not tool_calls:
            return {"answer": response_message.get("content", ""), "tools_called": tools_called}

        call = tool_calls[0]
        function = call.get("function", {})
        tool_name = function.get("name")
        arguments = function.get("arguments") or {}

        try:
            result = await dispatch(tool_name, db=db, user_id=user_id, **arguments)
            result_content = json.dumps(result)
        except (KeyError, ValueError, ToolPermissionError) as exc:
            result_content = json.dumps({"error": str(exc)})
            logger.info("manager agent tool call %r failed: %s", tool_name, exc)

        tools_called.append(tool_name)
        messages = [
            *messages,
            {"role": "assistant", "content": "", "tool_calls": tool_calls},
            {"role": "tool", "content": result_content},
        ]

    answer = await chat_completion(messages, user_id=user_id, endpoint="manager_agent")
    return {"answer": answer, "tools_called": tools_called}
```

Note this still runs a final `chat_completion()` synthesis call when the round cap is hit (rather than a hardcoded string), so the model gets to explain what it found across all the rounds it did complete — closer to today's "explain the failure in its final answer" behavior than a canned message would be.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd services/api && python -m pytest tests/test_manager_agent.py -v`
Expected: PASS, including all pre-existing tests from Tasks 1-3 (the single-tool-call tests are a special case of the loop: one round, then `tool_calls` is empty on round two so it returns immediately — confirm this by reading the passing output, not just trusting it).

- [ ] **Step 5: Run the full backend suite**

Run: `cd services/api && python -m pytest tests/ -x`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/manager_agent.py services/api/tests/test_manager_agent.py
git commit -m "feat: manager agent chains up to 5 tool calls per request instead of one

Enables compound requests like 'look up this plate, then draft a
letter to the owner'. Per-round error handling unchanged -- a failed
dispatch still feeds an {error: ...} tool-result back to the model,
now just within a loop instead of a single pass."
```

---

### Task 5: Terminal-tool handling for `answer_from_documents` and `draft_legal_document`

**Files:**
- Modify: `services/api/src/api/manager_agent.py`, `services/api/src/api/manager_router.py`
- Test: `services/api/tests/test_manager_agent.py`, `services/api/tests/test_manager_router.py`

**Interfaces:**
- Consumes: `api.legal.DraftResponse` (existing, from `api.legal`), `api.chat.Citation` (existing, Task 1).
- Produces: `handle_request()` can return two new optional keys, `citations: list[Citation] | None` and `legal_draft: DraftResponse | None`, alongside `answer`/`tools_called`. `AskResponse` gains matching optional fields.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_manager_agent.py`:

```python
async def test_handle_request_treats_answer_from_documents_as_terminal():
    from api.chat import Citation, GroundedAnswer

    user = await _create_user(_unique("manageruser"))
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "answer_from_documents", "arguments": {"message": "what is x"}}}],
    }
    fake_answer = GroundedAnswer(
        answer="grounded answer", citations=[Citation(marker=1, document_id=uuid4(), document_title="t", chunk_id=uuid4())],
    )

    async with async_session() as db:
        with (
            patch("api.manager_agent.chat_completion_with_tools", return_value=tool_call_response) as mock_with_tools,
            patch("api.tools.answer_grounded_question", return_value=fake_answer),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="what is x")

    assert result["answer"] == "grounded answer"
    assert result["tools_called"] == ["answer_from_documents"]
    assert result["citations"][0].document_title == "t"
    assert result.get("legal_draft") is None
    mock_with_tools.assert_called_once()  # no second round-trip to re-synthesize


async def test_handle_request_treats_draft_legal_document_as_terminal():
    from api.legal import DraftResponse

    user = await _create_user(_unique("manageruser"))
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "draft_legal_document", "arguments": {"instruction": "draft a letter"}}}],
    }
    fake_draft = DraftResponse(draft="Dear Sir or Madam...", citations=[])

    async with async_session() as db:
        with (
            patch("api.manager_agent.chat_completion_with_tools", return_value=tool_call_response) as mock_with_tools,
            patch("api.tools._generate_draft", return_value=fake_draft),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="draft a letter")

    assert result["answer"] == "Dear Sir or Madam..."
    assert result["tools_called"] == ["draft_legal_document"]
    assert result["legal_draft"].disclaimer
    mock_with_tools.assert_called_once()


async def test_handle_request_non_terminal_tool_still_gets_a_synthesis_round():
    user = await _create_user(_unique("manageruser"))
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hello"}}}],
    }
    final_response = {"content": "synthesized"}

    async with async_session() as db:
        with (
            patch(
                "api.manager_agent.chat_completion_with_tools",
                side_effect=[tool_call_response, final_response],
            ) as mock_with_tools,
            patch("api.tools.hybrid_search", return_value=[]),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="find hello")

    assert result["answer"] == "synthesized"
    assert result.get("citations") is None
    assert result.get("legal_draft") is None
    # search is non-terminal: the loop needs a second chat_completion_with_tools
    # call (which happens to return no tool_calls this time) to produce a final
    # answer, unlike the terminal-tool tests above which return after one call.
    assert mock_with_tools.call_count == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/api && python -m pytest tests/test_manager_agent.py -k "terminal" -v`
Expected: FAIL — `result["citations"]` and `result["legal_draft"]` don't exist yet (`KeyError` via `.get()` returning `None` is fine for the negative assertions, but the positive ones in the first two tests will fail).

- [ ] **Step 3: Implement terminal-tool handling**

In `services/api/src/api/manager_agent.py`, add the imports:

```python
from api.chat import Citation
from api.legal import DraftResponse
```

Add a constant naming the terminal tools, and change the loop body to check for them right after a successful dispatch:

```python
TERMINAL_TOOLS = {"answer_from_documents", "draft_legal_document"}
```

Replace the loop's dispatch section (inside the `for _round in range(MAX_TOOL_ROUNDS):` block, everything from `call = tool_calls[0]` through the end of the loop body) with:

```python
        call = tool_calls[0]
        function = call.get("function", {})
        tool_name = function.get("name")
        arguments = function.get("arguments") or {}

        try:
            result = await dispatch(tool_name, db=db, user_id=user_id, **arguments)
        except (KeyError, ValueError, ToolPermissionError) as exc:
            logger.info("manager agent tool call %r failed: %s", tool_name, exc)
            tools_called.append(tool_name)
            messages = [
                *messages,
                {"role": "assistant", "content": "", "tool_calls": tool_calls},
                {"role": "tool", "content": json.dumps({"error": str(exc)})},
            ]
            continue

        tools_called.append(tool_name)

        if tool_name in TERMINAL_TOOLS:
            if tool_name == "answer_from_documents":
                return {
                    "answer": result["answer"],
                    "tools_called": tools_called,
                    "citations": [Citation(**c) for c in result["citations"]],
                    "legal_draft": None,
                }
            return {  # tool_name == "draft_legal_document"
                "answer": result["draft"],
                "tools_called": tools_called,
                "citations": None,
                "legal_draft": DraftResponse(**result),
            }

        messages = [
            *messages,
            {"role": "assistant", "content": "", "tool_calls": tool_calls},
            {"role": "tool", "content": json.dumps(result)},
        ]
```

Note the error-handling branch now uses `continue` to move to the next loop iteration directly, rather than falling through to the terminal-tool checks (a failed dispatch never produces a `result` dict to check the tool name against).

Update the two earlier `return` statements in `handle_request()` (the no-permitted-tools case and the no-tool-requested case) to include the two new keys for consistent response shape:

```python
    tools = _tools_for_role(role)
    if not tools:
        answer = await chat_completion(messages, user_id=user_id, endpoint="manager_agent")
        return {"answer": answer, "tools_called": [], "citations": None, "legal_draft": None}

    tools_called: list[str] = []
    for _round in range(MAX_TOOL_ROUNDS):
        response_message = await chat_completion_with_tools(
            messages, user_id=user_id, endpoint="manager_agent", tools=tools,
        )
        tool_calls = response_message.get("tool_calls")
        if not tool_calls:
            return {
                "answer": response_message.get("content", ""), "tools_called": tools_called,
                "citations": None, "legal_draft": None,
            }
```

And the round-cap-exceeded fallback at the end of the function:

```python
    answer = await chat_completion(messages, user_id=user_id, endpoint="manager_agent")
    return {"answer": answer, "tools_called": tools_called, "citations": None, "legal_draft": None}
```

- [ ] **Step 4: Update `AskResponse`**

In `services/api/src/api/manager_router.py`:

```python
from api.chat import Citation
from api.legal import DraftResponse

class AskResponse(BaseModel):
    answer: str
    tools_called: list[str]
    citations: list[Citation] | None = None
    legal_draft: DraftResponse | None = None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd services/api && python -m pytest tests/test_manager_agent.py tests/test_manager_router.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `cd services/api && python -m pytest tests/ -x`
Expected: PASS, full count.

- [ ] **Step 7: Deploy and verify live (this project's standing discipline)**

Following the isolated scratch-dir + throwaway Docker container pattern used for every prior phase in this project: sync `chat.py`, `tools.py`, `manager_agent.py`, `manager_router.py` to the live `api` container, run the full test suite there too, then a real Playwright/QA-session check hitting `/manager/ask` with a message that should trigger `answer_from_documents` and one that should trigger `draft_legal_document`, confirming `tools_called`/`citations`/`legal_draft` come back populated as designed — not just that the unit tests pass in isolation.

- [ ] **Step 8: Write the ADR and commit**

Write `docs/adr/00XX-manager-agent-multiround.md` (check `docs/adr/` for the next free number — do not hardcode one here, it will have moved on by execution time) covering: what changed, why `answer_from_documents` is a new tool rather than changing `search`'s behavior, why two tools are terminal and the rest aren't, and the live verification performed.

```bash
git add services/api/src/api/chat.py services/api/src/api/tools.py services/api/src/api/manager_agent.py services/api/src/api/manager_router.py services/api/tests/ docs/adr/00XX-manager-agent-multiround.md
git commit -m "feat: answer_from_documents and draft_legal_document are terminal tools

Both already produce a finished, grounded/disclaimer-bearing result --
dispatching either now ends the loop immediately with that result
instead of spending another model round re-synthesizing an answer
that was already correct. Closes out the backend half of the chat
consolidation (see docs/superpowers/specs/2026-07-10-unified-chat-consolidation-design.md);
Signal wiring and frontend consolidation are separate follow-on plans."
```
