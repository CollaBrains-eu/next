# Wire UserFacts into chat and legal drafting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a user's currently-valid, admin-confirmed `UserFact` rows visible to the model in `/chat`, `/legal/draft`, and both Manager Agent tools that wrap them (`answer_from_documents`, `draft_legal_document`) — closing the gap where facts are extracted, reviewed, and then never read again.

**Architecture:** One new read function in `user_facts.py`; two call-site changes, one each in `chat.py`'s `answer_grounded_question` and `legal.py`'s `_generate_draft` — the two shared functions already behind all four AI-facing entry points, so no new endpoints or Manager Agent tool schema changes are needed.

**Tech Stack:** FastAPI + SQLAlchemy (async), pytest + httpx.AsyncClient, existing `UserFact` model (Phase 26).

## Global Constraints

- Only `status == "confirmed"` facts are ever read by `get_current_facts` — `pending_review` and `rejected` facts must never reach a generated answer.
- "Currently valid" means `valid_from <= today` AND (`valid_to` is null OR `valid_to >= today`).
- Facts retrieval failing must never fail the chat/draft response — wrap in `try/except Exception` and fall back to an empty list, logging via `logger.exception`, matching the existing pattern every other optional context source in these two functions already follows (memory retrieval, preference lookup).
- Facts are injected as a distinct labeled block ("Known facts about the user:") — never merged into the document `Context:` block, to keep citation markers unambiguous.
- Full design rationale lives in `docs/superpowers/specs/2026-07-18-wire-user-facts-design.md` — this plan implements it; consult it only if a step here is ambiguous.
- Backend tests run via `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest <path> -v` (pytest is already installed in the container from earlier work this session — reinstall only if you get a "not found" error: `docker compose exec -T api uv pip install --system --no-cache pytest pytest-asyncio`).

---

### Task 1: `get_current_facts` read function

**Files:**
- Modify: `services/api/src/api/user_facts.py`
- Test: `services/api/tests/test_user_facts.py`

**Interfaces:**
- Produces: `get_current_facts(db: AsyncSession, *, user_id: UUID) -> list[UserFact]`. Tasks 2 and 3 both import and call this.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_user_facts.py`, after the existing imports (add `UserFact` to the `from api.models import Document, User` line, making it `from api.models import Document, User, UserFact`) and after the existing `_create_document` helper:

```python
async def _create_fact(
    user_id, *, fact_type: str = "address", value: str = "Kerkstraat 1, Amsterdam",
    valid_from: date = date(2020, 1, 1), valid_to: date | None = None, status: str = "confirmed",
) -> UserFact:
    async with async_session() as db:
        fact = UserFact(
            user_id=user_id, fact_type=fact_type, value={"text": value},
            valid_from=valid_from, valid_to=valid_to, status=status,
        )
        db.add(fact)
        await db.commit()
        await db.refresh(fact)
        return fact
```

Then add the test cases at the end of the file:

```python
async def test_get_current_facts_returns_a_confirmed_fact_valid_today():
    user = await _create_user(_unique("currentfactuser1"))
    await _create_fact(user.id, status="confirmed")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert len(facts) == 1
    assert facts[0].fact_type == "address"


async def test_get_current_facts_excludes_pending_review_facts():
    user = await _create_user(_unique("currentfactuser2"))
    await _create_fact(user.id, status="pending_review")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert facts == []


async def test_get_current_facts_excludes_rejected_facts():
    user = await _create_user(_unique("currentfactuser3"))
    await _create_fact(user.id, status="rejected")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert facts == []


async def test_get_current_facts_excludes_a_fact_whose_valid_to_has_passed():
    user = await _create_user(_unique("currentfactuser4"))
    await _create_fact(user.id, valid_from=date(2020, 1, 1), valid_to=date(2021, 1, 1), status="confirmed")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert facts == []


async def test_get_current_facts_excludes_a_fact_not_yet_valid():
    user = await _create_user(_unique("currentfactuser5"))
    await _create_fact(user.id, valid_from=date(2099, 1, 1), valid_to=None, status="confirmed")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert facts == []


async def test_get_current_facts_includes_an_open_ended_fact_started_in_the_past():
    user = await _create_user(_unique("currentfactuser6"))
    await _create_fact(user.id, valid_from=date(2020, 1, 1), valid_to=None, status="confirmed")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert len(facts) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_user_facts.py -v -k current_facts`
Expected: FAIL — `get_current_facts` is not defined, and `date`/`get_current_facts` are not yet imported in the test file

- [ ] **Step 3: Add the required test-file imports**

At the top of `services/api/tests/test_user_facts.py`, change:

```python
from api.models import Document, User
from api.user_facts import detect_conflicts, extract_facts_from_document
```

to:

```python
from api.models import Document, User, UserFact
from api.user_facts import detect_conflicts, extract_facts_from_document, get_current_facts
```

(`date` is already imported at the top of this file — no change needed there.)

- [ ] **Step 4: Write the implementation**

In `services/api/src/api/user_facts.py`, add after `detect_conflicts` (before `extract_facts_from_document`):

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

(`or_`, `select`, `date`, and `UserFact` are all already imported at the top of `user_facts.py` — no new imports needed in the implementation file.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_user_facts.py -v`
Expected: PASS, all tests (13/13 — 7 pre-existing + 6 new)

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/user_facts.py services/api/tests/test_user_facts.py
git commit -m "feat(facts): add get_current_facts read function"
```

---

### Task 2: Wire facts into `/chat`

**Files:**
- Modify: `services/api/src/api/chat.py`
- Test: `services/api/tests/test_chat.py`

**Interfaces:**
- Consumes: `get_current_facts` from `api.user_facts` (Task 1).

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_chat.py`, after the existing `test_chat_omits_language_instruction_when_no_preference_set` test (find it by name; add these two tests directly after it, before the on-behalf-of tests):

```python
async def test_chat_includes_a_confirmed_fact_in_the_prompt(client):
    from datetime import date

    from api.db import async_session
    from api.models import User, UserFact

    token = await _login_as(client, "chatfactuser1")
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == "chatfactuser1"))).scalar_one()
        db.add(UserFact(
            user_id=user.id, fact_type="address", value={"text": "Kerkstraat 1, Amsterdam"},
            valid_from=date(2020, 1, 1), valid_to=None, status="confirmed",
        ))
        await db.commit()

    with (
        patch("api.chat.hybrid_search", return_value=[]),
        patch("api.chat.chat_completion", return_value="ok") as mock_completion,
    ):
        await client.post("/chat", headers=headers, json={"message": "What is my address?"})

    sent_messages = mock_completion.call_args.args[0]
    user_message = sent_messages[-1]["content"]
    assert "Known facts about the user:" in user_message
    assert "address: Kerkstraat 1, Amsterdam" in user_message


async def test_chat_excludes_a_pending_review_fact_from_the_prompt(client):
    from datetime import date

    from api.db import async_session
    from api.models import User, UserFact

    token = await _login_as(client, "chatfactuser2")
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == "chatfactuser2"))).scalar_one()
        db.add(UserFact(
            user_id=user.id, fact_type="employer", value={"text": "Acme BV"},
            valid_from=date(2020, 1, 1), valid_to=None, status="pending_review",
        ))
        await db.commit()

    with (
        patch("api.chat.hybrid_search", return_value=[]),
        patch("api.chat.chat_completion", return_value="ok") as mock_completion,
    ):
        await client.post("/chat", headers=headers, json={"message": "hello"})

    sent_messages = mock_completion.call_args.args[0]
    user_message = sent_messages[-1]["content"]
    assert "Known facts about the user:" not in user_message
    assert "Acme BV" not in user_message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_chat.py -v -k fact`
Expected: FAIL — the "Known facts about the user:" block does not exist yet, so the first test's assertions fail (and the second test currently passes vacuously since nothing injects facts at all yet — that's expected; it becomes a real assertion once Step 3 lands)

- [ ] **Step 3: Add the import**

In `services/api/src/api/chat.py`, change:

```python
from api.memory import maybe_create_memory_from_exchange, reinforce_memories, retrieve_relevant_memories
```

to:

```python
from api.memory import maybe_create_memory_from_exchange, reinforce_memories, retrieve_relevant_memories
from api.user_facts import get_current_facts
```

- [ ] **Step 4: Add facts retrieval to `answer_grounded_question`**

In `services/api/src/api/chat.py`, `answer_grounded_question` currently has this block right after the memory-retrieval block:

```python
    try:
        memories = await retrieve_relevant_memories(db, user_id=user_id, query=message)
    except Exception:  # noqa: BLE001 - memory retrieval must never fail the answer
        logger.exception("memory retrieval failed for grounded question")
        memories = []

    memory_text = ""
    if memories:
        memory_lines = "\n".join(f"- {memory.summary}" for memory in memories)
        memory_text = f"\n\nRelevant memories:\n{memory_lines}"
```

Add a facts-retrieval block immediately after it (before the `language_instruction` block):

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

- [ ] **Step 5: Thread `facts_text` through `_build_messages`**

In `services/api/src/api/chat.py`, `_build_messages` currently is:

```python
def _build_messages(
    history: list[ChatTurn], context_text: str, question: str, memory_text: str = "",
    language_instruction: str = "",
) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT + language_instruction}]
    messages.extend({"role": turn.role, "content": turn.content} for turn in history)
    messages.append({"role": "user", "content": f"Context:\n{context_text}{memory_text}\n\nQuestion: {question}"})
    return messages
```

Change to:

```python
def _build_messages(
    history: list[ChatTurn], context_text: str, question: str, memory_text: str = "",
    language_instruction: str = "", facts_text: str = "",
) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT + language_instruction}]
    messages.extend({"role": turn.role, "content": turn.content} for turn in history)
    messages.append({"role": "user", "content": f"Context:\n{context_text}{facts_text}{memory_text}\n\nQuestion: {question}"})
    return messages
```

Both call sites inside `answer_grounded_question` currently read:

```python
    messages = _build_messages(history, context_text, message, memory_text, language_instruction)
```

(this exact line appears twice — once before the initial `chat_completion` call, once inside the reflection-retry block). Change **both occurrences** to:

```python
    messages = _build_messages(history, context_text, message, memory_text, language_instruction, facts_text)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_chat.py -v`
Expected: PASS, all tests

- [ ] **Step 7: Commit**

```bash
git add services/api/src/api/chat.py services/api/tests/test_chat.py
git commit -m "feat(chat): inject confirmed user facts into the answer prompt"
```

---

### Task 3: Wire facts into `/legal/draft`

**Files:**
- Modify: `services/api/src/api/legal.py`
- Test: `services/api/tests/test_legal.py`

**Interfaces:**
- Consumes: `get_current_facts` from `api.user_facts` (Task 1).

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_legal.py`, after the existing `test_draft_includes_preferred_language_in_system_prompt` test (at the end of the file):

```python
async def test_draft_includes_a_confirmed_fact_in_the_prompt(client):
    from datetime import date

    from api.db import async_session
    from api.models import User, UserFact

    token = await _login_as_legal(client, "legalfactuser1")
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == "legalfactuser1"))).scalar_one()
        db.add(UserFact(
            user_id=user.id, fact_type="address", value={"text": "Kerkstraat 1, Amsterdam"},
            valid_from=date(2020, 1, 1), valid_to=None, status="confirmed",
        ))
        await db.commit()

    with (
        patch("api.legal.hybrid_search", return_value=[]),
        patch("api.legal.chat_completion", return_value="ok") as mock_completion,
    ):
        await client.post("/legal/draft", headers=headers, json={"instruction": "Draft a change-of-address notice."})

    sent_messages = mock_completion.call_args.args[0]
    user_message = sent_messages[-1]["content"]
    assert "Known facts about the user:" in user_message
    assert "address: Kerkstraat 1, Amsterdam" in user_message


async def test_draft_excludes_a_pending_review_fact_from_the_prompt(client):
    from datetime import date

    from api.db import async_session
    from api.models import User, UserFact

    token = await _login_as_legal(client, "legalfactuser2")
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == "legalfactuser2"))).scalar_one()
        db.add(UserFact(
            user_id=user.id, fact_type="employer", value={"text": "Acme BV"},
            valid_from=date(2020, 1, 1), valid_to=None, status="pending_review",
        ))
        await db.commit()

    with (
        patch("api.legal.hybrid_search", return_value=[]),
        patch("api.legal.chat_completion", return_value="ok") as mock_completion,
    ):
        await client.post("/legal/draft", headers=headers, json={"instruction": "Draft anything."})

    sent_messages = mock_completion.call_args.args[0]
    user_message = sent_messages[-1]["content"]
    assert "Known facts about the user:" not in user_message
    assert "Acme BV" not in user_message
```

This test file's existing `_login` helper always logs in as the fixed username `"legaluser"` (no parameter), which would collide with itself across these two new tests if reused directly. Add a small parameterized variant right after the existing `_login` function:

```python
async def _login_as_legal(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_legal.py -v -k fact`
Expected: FAIL — the "Known facts about the user:" block does not exist yet

- [ ] **Step 3: Add the import**

In `services/api/src/api/legal.py`, change:

```python
from api.reflection import log_reflection, reflect
```

to:

```python
from api.reflection import log_reflection, reflect
from api.user_facts import get_current_facts
```

- [ ] **Step 4: Add facts retrieval and thread it through both message-building sites**

In `services/api/src/api/legal.py`, `_generate_draft` currently starts:

```python
async def _generate_draft(
    db: AsyncSession, *, instruction: str, user_id: UUID, document_ids: list[UUID] | None = None,
    context_chunks: int = 8,
) -> DraftResponse:
    scope = set(document_ids) if document_ids else None
    citations, context_text = await _retrieve(db, instruction, context_chunks, scope, user_id)

    language_instruction = ""
```

Insert a facts-retrieval block between the `_retrieve` call and the `language_instruction` line:

```python
async def _generate_draft(
    db: AsyncSession, *, instruction: str, user_id: UUID, document_ids: list[UUID] | None = None,
    context_chunks: int = 8,
) -> DraftResponse:
    scope = set(document_ids) if document_ids else None
    citations, context_text = await _retrieve(db, instruction, context_chunks, scope, user_id)

    try:
        facts = await get_current_facts(db, user_id=user_id)
    except Exception:  # noqa: BLE001 - facts retrieval must never fail the draft response
        logger.exception("facts retrieval failed for legal draft request")
        facts = []

    facts_text = ""
    if facts:
        fact_lines = "\n".join(f"- {fact.fact_type}: {fact.value.get('text', '')}" for fact in facts)
        facts_text = f"\n\nKnown facts about the user:\n{fact_lines}"

    language_instruction = ""
```

Both `messages = [...]` constructions in this function currently read:

```python
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + language_instruction},
        {"role": "user", "content": f"Context:\n{context_text}\n\nDrafting instruction: {instruction}"},
    ]
```

(this exact block appears twice — once before the initial `chat_completion` call, once inside the reflection-retry block). Change **both occurrences'** second line to:

```python
        {"role": "user", "content": f"Context:\n{context_text}{facts_text}\n\nDrafting instruction: {instruction}"},
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_legal.py -v`
Expected: PASS, all tests

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/legal.py services/api/tests/test_legal.py
git commit -m "feat(legal): inject confirmed user facts into the draft prompt"
```

---

### Task 4: Full verification and deploy

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests -v 2>&1 | tail -60`
Expected: all pass except the pre-existing, unrelated test-DB-pollution failures already documented this session (~28 failures spanning entities/appointments/AI-gateway/tasks/chat, none touching facts/chat-prompt/legal-prompt logic — confirmed via the same method used earlier today: `git diff` against the pre-Task-1 commit shows these tests' bodies are unchanged, and the failures reproduce in isolation). If any *other* test fails, stop and investigate before continuing.

- [ ] **Step 2: Rebuild and deploy**

```bash
docker compose build api
docker compose up -d api
```

(No migration needed — `UserFact` and its `facts` route already existed before this plan; this plan only adds a new read function and two prompt-injection call sites, no schema change.)

Confirm the container is healthy: `docker compose ps api --format '{{.Service}} {{.Status}}'`

- [ ] **Step 3: Live verification**

Using a disposable test user (create one via LDAP admin-bind, matching this session's established `ldap_auth.create_user` pattern for disposable test accounts — do not reuse a real pilot user's account for this):

1. Directly insert a confirmed `UserFact` for the test user (e.g. `fact_type="address"`, a recognizable test value, `status="confirmed"`, `valid_from` in the past, `valid_to` null).
2. Log in as the test user, send a `/chat` message asking a question unrelated to the fact (e.g. "hello") and inspect the request the API actually sent to the model (via the `ai_call_log` table or a temporary log statement) to confirm the "Known facts about the user:" block with the test fact appears.
3. Send a `/legal/draft` request as the same test user and confirm the same block appears in that prompt too.
4. Flip the test fact's `status` to `pending_review` directly in the database and repeat both checks — confirm the block is now absent from both.
5. Delete the disposable test user (LDAP + Postgres, including the test `UserFact` row) afterward, same cleanup discipline as every other phase's live testing this session.

- [ ] **Step 4: Commit and push**

```bash
git push origin main
```
