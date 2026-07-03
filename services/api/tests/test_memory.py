import uuid as uuid_module
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.memory import (
    create_memory,
    delete_memory,
    maybe_create_memory_from_exchange,
    reinforce_memories,
    retrieve_relevant_memories,
)
from api.models import Memory, User

FAKE_EMBEDDING = [0.1] * 768


def _unique(base: str) -> str:
    """Append a per-call random suffix so reruns against this persistent test DB never collide."""
    return f"{base}-{uuid_module.uuid4().hex[:8]}"


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _login_unique(client, base_username: str) -> tuple[str, str]:
    username = _unique(base_username)
    token = await _login(client, username)
    return token, username


async def _make_user(username: str) -> User:
    username = _unique(username)
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def test_create_memory_persists_with_embedding():
    user = await _make_user("mem-create-user")

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            memory = await create_memory(
                db, user_id=user.id, memory_type="semantic", summary="Prefers Signal notifications.", importance=70
            )

    assert memory.memory_type == "semantic"
    assert memory.importance == 70
    assert memory.summary == "Prefers Signal notifications."

    async with async_session() as db:
        stored = await db.get(Memory, memory.id)
        assert stored is not None
        assert stored.user_id == user.id


async def test_create_memory_rejects_invalid_memory_type():
    user = await _make_user("mem-invalid-type-user")

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            try:
                await create_memory(db, user_id=user.id, memory_type="bogus", summary="x")
                assert False, "expected ValueError"
            except ValueError:
                pass


async def test_retrieve_relevant_memories_scoped_to_user_and_touches_last_used_at():
    owner = await _make_user("mem-retrieve-owner")
    other = await _make_user("mem-retrieve-other")

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            await create_memory(db, user_id=owner.id, memory_type="episodic", summary="Owner's memory")
        async with async_session() as db:
            await create_memory(db, user_id=other.id, memory_type="episodic", summary="Other user's memory")

        async with async_session() as db:
            results = await retrieve_relevant_memories(db, user_id=owner.id, query="anything")

    assert [m.summary for m in results] == ["Owner's memory"]
    assert results[0].last_used_at is not None


async def test_retrieve_relevant_memories_excludes_expired():
    user = await _make_user("mem-expired-user")
    past = datetime.now(timezone.utc) - timedelta(days=1)

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            await create_memory(db, user_id=user.id, memory_type="episodic", summary="Expired", expires_at=past)
            await create_memory(db, user_id=user.id, memory_type="episodic", summary="Still valid")

        async with async_session() as db:
            results = await retrieve_relevant_memories(db, user_id=user.id, query="anything")

    assert [m.summary for m in results] == ["Still valid"]


async def test_delete_memory_removes_it_for_owner():
    user = await _make_user("mem-delete-owner")

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            memory = await create_memory(db, user_id=user.id, memory_type="episodic", summary="Delete me")

    async with async_session() as db:
        deleted = await delete_memory(db, memory_id=memory.id, user_id=user.id)
    assert deleted is True

    async with async_session() as db:
        assert await db.get(Memory, memory.id) is None


async def test_delete_memory_rejects_non_owner_non_admin():
    owner = await _make_user("mem-delete-owner-2")
    other = await _make_user("mem-delete-other-2")

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            memory = await create_memory(db, user_id=owner.id, memory_type="episodic", summary="Not yours")

    async with async_session() as db:
        deleted = await delete_memory(db, memory_id=memory.id, user_id=other.id)
    assert deleted is False

    async with async_session() as db:
        assert await db.get(Memory, memory.id) is not None


async def test_maybe_create_memory_skips_when_not_worth_remembering():
    user = await _make_user("mem-extract-skip-user")
    fake_decision = '{"should_remember": false, "memory_type": "episodic", "summary": "", "importance": 0}'

    with patch("api.memory.chat_completion", return_value=fake_decision):
        async with async_session() as db:
            result = await maybe_create_memory_from_exchange(
                db, user_id=user.id, user_message="What's the capital of France?", answer="Paris."
            )

    assert result is None

    async with async_session() as db:
        rows = (await db.execute(select(Memory).where(Memory.user_id == user.id))).scalars().all()
    assert rows == []


async def test_maybe_create_memory_persists_when_worth_remembering():
    user = await _make_user("mem-extract-create-user")
    fake_decision = (
        '{"should_remember": true, "memory_type": "semantic", '
        '"summary": "User has an active objection procedure.", "importance": 95}'
    )

    with (
        patch("api.memory.chat_completion", return_value=fake_decision),
        patch("api.memory.embed_text", return_value=FAKE_EMBEDDING),
    ):
        async with async_session() as db:
            result = await maybe_create_memory_from_exchange(
                db, user_id=user.id, user_message="I filed an objection last week.", answer="Noted."
            )

    assert result is not None
    assert result.memory_type == "semantic"
    assert result.importance == 95
    assert result.summary == "User has an active objection procedure."


async def test_maybe_create_memory_handles_unparseable_output_gracefully():
    user = await _make_user("mem-extract-garbage-user")

    with patch("api.memory.chat_completion", return_value="not json at all"):
        async with async_session() as db:
            result = await maybe_create_memory_from_exchange(
                db, user_id=user.id, user_message="hello", answer="hi"
            )

    assert result is None


async def test_reinforce_memories_increases_importance():
    user = await _make_user("mem-reinforce-user")

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            memory = await create_memory(
                db, user_id=user.id, memory_type="semantic", summary="x", importance=50
            )

    async with async_session() as db:
        await reinforce_memories(db, [memory.id], delta=5)

    async with async_session() as db:
        refreshed = await db.get(Memory, memory.id)
        assert refreshed.importance == 55


async def test_reinforce_memories_caps_at_100():
    user = await _make_user("mem-reinforce-cap-user")

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            memory = await create_memory(
                db, user_id=user.id, memory_type="semantic", summary="x", importance=98
            )

    async with async_session() as db:
        await reinforce_memories(db, [memory.id], delta=5)

    async with async_session() as db:
        refreshed = await db.get(Memory, memory.id)
        assert refreshed.importance == 100


async def test_reinforce_memories_handles_empty_list_without_error():
    # should return before ever touching db, so a bogus db value is fine here
    await reinforce_memories(None, [])


async def test_chat_includes_relevant_memories_in_prompt_context(client):
    token, username = await _login_unique(client, "mem-chat-user")
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session() as db:
        chat_user = (await db.execute(select(User).where(User.username == username))).scalar_one()

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            await create_memory(
                db, user_id=chat_user.id, memory_type="semantic", summary="User prefers concise answers."
            )

    with (
        patch("api.chat.hybrid_search", return_value=[]),
        patch("api.chat.retrieve_relevant_memories", wraps=retrieve_relevant_memories) as mock_retrieve,
        patch("api.memory.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.chat.chat_completion", return_value="ok") as mock_completion,
        patch("api.memory.chat_completion", return_value='{"should_remember": false}'),
    ):
        response = await client.post("/chat", headers=headers, json={"message": "How should I format replies?"})

    assert response.status_code == 200
    mock_retrieve.assert_called_once()
    sent_messages = mock_completion.call_args.args[0]
    user_turn = sent_messages[-1]["content"]
    assert "Relevant memories:" in user_turn
    assert "User prefers concise answers." in user_turn


async def test_chat_reinforces_memories_used_in_a_sufficient_answer(client):
    from api.reflection import ReflectionResult

    token, username = await _login_unique(client, "mem-reinforce-chat-user")
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session() as db:
        chat_user = (await db.execute(select(User).where(User.username == username))).scalar_one()

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            memory = await create_memory(
                db, user_id=chat_user.id, memory_type="semantic", summary="Relevant fact.", importance=50
            )

    with (
        patch("api.chat.hybrid_search", return_value=[]),
        patch("api.chat.retrieve_relevant_memories", wraps=retrieve_relevant_memories),
        patch("api.memory.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.chat.chat_completion", return_value="ok"),
        patch("api.memory.chat_completion", return_value='{"should_remember": false}'),
        patch(
            "api.chat.reflect",
            return_value=ReflectionResult(sufficient_evidence=True, confidence=90, issues=[]),
        ),
    ):
        response = await client.post("/chat", headers=headers, json={"message": "What's the relevant fact?"})

    assert response.status_code == 200

    async with async_session() as db:
        refreshed = await db.get(Memory, memory.id)
    assert refreshed.importance == 55


async def test_chat_does_not_reinforce_memories_on_insufficient_evidence(client):
    from api.reflection import ReflectionResult

    token, username = await _login_unique(client, "mem-no-reinforce-user")
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session() as db:
        chat_user = (await db.execute(select(User).where(User.username == username))).scalar_one()

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            memory = await create_memory(
                db, user_id=chat_user.id, memory_type="semantic", summary="Relevant fact.", importance=50
            )

    with (
        patch("api.chat.hybrid_search", return_value=[]),
        patch("api.chat.retrieve_relevant_memories", wraps=retrieve_relevant_memories),
        patch("api.memory.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.chat.chat_completion", return_value="ok"),
        patch("api.memory.chat_completion", return_value='{"should_remember": false}'),
        patch(
            "api.chat.reflect",
            return_value=ReflectionResult(sufficient_evidence=False, confidence=20, issues=["no evidence"]),
        ),
    ):
        response = await client.post("/chat", headers=headers, json={"message": "What's the relevant fact?"})

    assert response.status_code == 200

    async with async_session() as db:
        refreshed = await db.get(Memory, memory.id)
    assert refreshed.importance == 50


async def test_list_and_delete_memories_via_api(client):
    token, username = await _login_unique(client, "mem-api-user")
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session() as db:
        api_user = (await db.execute(select(User).where(User.username == username))).scalar_one()

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            memory = await create_memory(db, user_id=api_user.id, memory_type="episodic", summary="Listable memory")

    listing = await client.get("/memories", headers=headers)
    assert listing.status_code == 200
    summaries = [m["summary"] for m in listing.json()]
    assert "Listable memory" in summaries

    delete_response = await client.delete(f"/memories/{memory.id}", headers=headers)
    assert delete_response.status_code == 204

    listing_after = await client.get("/memories", headers=headers)
    assert all(m["id"] != str(memory.id) for m in listing_after.json())


async def test_delete_memory_endpoint_rejects_other_users_memory(client):
    owner_token, owner_username = await _login_unique(client, "mem-api-owner")
    headers_owner = {"Authorization": f"Bearer {owner_token}"}
    other_token, _ = await _login_unique(client, "mem-api-intruder")
    headers_other = {"Authorization": f"Bearer {other_token}"}

    async with async_session() as db:
        owner = (await db.execute(select(User).where(User.username == owner_username))).scalar_one()

    with patch("api.memory.embed_text", return_value=FAKE_EMBEDDING):
        async with async_session() as db:
            memory = await create_memory(db, user_id=owner.id, memory_type="episodic", summary="Owner only")

    response = await client.delete(f"/memories/{memory.id}", headers=headers_other)
    assert response.status_code == 404

    still_there = await client.get("/memories", headers=headers_owner)
    assert any(m["id"] == str(memory.id) for m in still_there.json())
