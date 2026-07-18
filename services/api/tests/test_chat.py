from unittest.mock import patch

from sqlalchemy import select

from api.ldap_auth import LdapIdentity
from api.reflection import ReflectionResult


async def _login(client) -> str:
    identity = LdapIdentity(
        username="chatuser", display_name="Chat User", email="chatuser@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "chatuser", "password": "whatever"})
    return response.json()["access_token"]


async def test_chat_returns_answer_with_citations(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.chat.hybrid_search", return_value=[]),
        patch("api.chat.chat_completion", return_value="I don't have relevant documents to answer that."),
    ):
        response = await client.post("/chat", headers=headers, json={"message": "What is our retention policy?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "I don't have relevant documents to answer that."
    assert body["citations"] == []


async def test_chat_rejects_missing_token(client):
    response = await client.post("/chat", json={"message": "hello"})
    assert response.status_code == 401


async def test_chat_includes_preferred_language_in_system_prompt(client):
    token = await _login_as(client, "chatprefuser1")
    headers = {"Authorization": f"Bearer {token}"}

    await client.put("/preferences/me", headers=headers, json={"preferred_language": "de"})

    with (
        patch("api.chat.hybrid_search", return_value=[]),
        patch("api.chat.chat_completion", return_value="ok") as mock_completion,
    ):
        await client.post("/chat", headers=headers, json={"message": "hello"})

    sent_messages = mock_completion.call_args.args[0]
    system_message = sent_messages[0]["content"]
    assert "you must respond only in de" in system_message.lower()


async def test_chat_omits_language_instruction_when_no_preference_set(client):
    token = await _login_as(client, "chatprefuser2")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.chat.hybrid_search", return_value=[]),
        patch("api.chat.chat_completion", return_value="ok") as mock_completion,
    ):
        await client.post("/chat", headers=headers, json={"message": "hello"})

    sent_messages = mock_completion.call_args.args[0]
    system_message = sent_messages[0]["content"]
    assert "Respond in" not in system_message


async def test_chat_retries_retrieval_when_reflection_flags_insufficient_evidence(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.chat.hybrid_search", side_effect=[[], []]) as mock_hybrid,
        patch("api.chat.chat_completion", side_effect=["first answer", "second answer"]) as mock_completion,
        patch(
            "api.chat.reflect",
            return_value=ReflectionResult(sufficient_evidence=False, confidence=20, issues=["no evidence"]),
        ),
    ):
        response = await client.post("/chat", headers=headers, json={"message": "What is our retention policy?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "second answer"
    assert mock_hybrid.call_count == 2
    assert mock_hybrid.call_args_list[1].kwargs["limit"] == 10  # context_chunks default 5, doubled
    assert mock_completion.call_count == 2

    from api.db import async_session
    from api.models import ReflectionLog, User

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == "chatuser"))).scalar_one()
        rows = (
            await db.execute(select(ReflectionLog).where(ReflectionLog.user_id == user.id))
        ).scalars().all()
    assert any(row.retried is True for row in rows)


async def test_chat_does_not_retry_when_reflection_flags_sufficient_evidence(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.chat.hybrid_search", return_value=[]) as mock_hybrid,
        patch("api.chat.chat_completion", return_value="the only answer") as mock_completion,
        patch(
            "api.chat.reflect",
            return_value=ReflectionResult(sufficient_evidence=True, confidence=95, issues=[]),
        ),
    ):
        response = await client.post("/chat", headers=headers, json={"message": "What is our retention policy?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "the only answer"
    assert mock_hybrid.call_count == 1
    assert mock_completion.call_count == 1


async def _create_service_account_token(username: str = "test-signal-bot") -> str:
    """Insert a role=service user directly (no LDAP path provisions this role) and mint its JWT."""
    from api.auth import create_access_token
    from api.db import async_session
    from api.models import User

    async with async_session() as db:
        db.add(User(username=username, display_name=username, role="service"))
        await db.commit()
    return create_access_token(username, "service")


async def _link_phone(client, username: str, phone_number: str) -> None:
    token = await _login_as(client, username)
    await client.put("/auth/me/phone", headers={"Authorization": f"Bearer {token}"}, json={"phone_number": phone_number})


async def _login_as(client, username: str) -> str:
    from unittest.mock import patch

    from api.ldap_auth import LdapIdentity

    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_chat_on_behalf_of_header_resolves_linked_phone_number(client):
    await _link_phone(client, "linkeduser1", "+15559990001")
    service_token = await _create_service_account_token("test-signal-bot-1")

    with (
        patch("api.chat.hybrid_search", return_value=[]),
        patch("api.chat.chat_completion", return_value="answer") as mock_completion,
    ):
        response = await client.post(
            "/chat",
            headers={"Authorization": f"Bearer {service_token}", "X-On-Behalf-Of-Phone": "+15559990001"},
            json={"message": "hi"},
        )

    assert response.status_code == 200
    called_user_id = mock_completion.call_args.kwargs["user_id"]

    from api.db import async_session
    from api.models import User
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "linkeduser1"))
        linked_user = result.scalar_one()
    assert called_user_id == linked_user.id


async def test_chat_on_behalf_of_header_rejects_unlinked_phone_number(client):
    service_token = await _create_service_account_token("test-signal-bot-2")

    response = await client.post(
        "/chat",
        headers={"Authorization": f"Bearer {service_token}", "X-On-Behalf-Of-Phone": "+15559990999"},
        json={"message": "hi"},
    )
    assert response.status_code == 403


async def test_chat_on_behalf_of_header_rejects_deactivated_linked_user(client):
    """A deactivated user's linked phone number must not resolve via the
    signal-bot on-behalf-of channel either -- deactivation has to close
    every attribution path, not just the JWT one (see auth.py's
    get_current_user for the equivalent JWT-path check)."""
    from uuid import uuid4

    hex_suffix = uuid4().hex[:8]
    digit_suffix = str(uuid4().int)[:8]
    username = f"deactivatedlinkeduser-{hex_suffix}"
    phone_number = f"+1555{digit_suffix}"
    await _link_phone(client, username, phone_number)
    service_token = await _create_service_account_token(f"test-signal-bot-{hex_suffix}")

    from api.db import async_session
    from api.models import User
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one()
        user.is_active = False
        await db.commit()

    response = await client.post(
        "/chat",
        headers={"Authorization": f"Bearer {service_token}", "X-On-Behalf-Of-Phone": phone_number},
        json={"message": "hi"},
    )
    assert response.status_code == 403


async def test_chat_ignores_on_behalf_of_header_from_non_service_caller(client):
    """A regular authenticated user cannot impersonate anyone via the header (ADR 0006)."""
    await _link_phone(client, "linkeduser2", "+15559990002")
    normal_token = await _login_as(client, "normaluser1")

    with (
        patch("api.chat.hybrid_search", return_value=[]),
        patch("api.chat.chat_completion", return_value="answer") as mock_completion,
    ):
        response = await client.post(
            "/chat",
            headers={"Authorization": f"Bearer {normal_token}", "X-On-Behalf-Of-Phone": "+15559990002"},
            json={"message": "hi"},
        )

    assert response.status_code == 200
    called_user_id = mock_completion.call_args.kwargs["user_id"]

    from api.db import async_session
    from api.models import User
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "normaluser1"))
        caller = result.scalar_one()
    # answered as the actual caller, NOT as linkeduser2
    assert called_user_id == caller.id
