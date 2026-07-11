from unittest.mock import patch
from uuid import uuid4

from api.ldap_auth import LdapIdentity
from api.search_service import SearchHit


async def _login(client) -> str:
    identity = LdapIdentity(
        username="manageruser", display_name="Manager User", email="manageruser@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "manageruser", "password": "whatever"})
    return response.json()["access_token"]


async def test_ask_returns_a_direct_answer_when_no_tool_is_needed(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with patch("api.manager_agent.chat_completion_with_tools", return_value={"content": "hi there"}):
        response = await client.post("/manager/ask", headers=headers, json={"message": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "hi there"
    assert body["tools_called"] == []


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


async def test_ask_rejects_missing_token(client):
    response = await client.post("/manager/ask", json={"message": "hello"})
    assert response.status_code == 401


async def _create_service_account_token(username: str) -> str:
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
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_ask_on_behalf_of_header_resolves_linked_phone_number(client):
    await _link_phone(client, "manageruser-linked1", "+15559991001")
    service_token = await _create_service_account_token("test-signal-bot-manager-1")

    with patch(
        "api.manager_agent.chat_completion_with_tools", return_value={"content": "hi there"}
    ) as mock_completion:
        response = await client.post(
            "/manager/ask",
            headers={"Authorization": f"Bearer {service_token}", "X-On-Behalf-Of-Phone": "+15559991001"},
            json={"message": "hello"},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "hi there"

    called_user_id = mock_completion.call_args.kwargs["user_id"]

    from api.db import async_session
    from api.models import User
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "manageruser-linked1"))
        linked_user = result.scalar_one()
    assert called_user_id == linked_user.id


async def test_ask_on_behalf_of_header_rejects_unlinked_phone_number(client):
    service_token = await _create_service_account_token("test-signal-bot-manager-2")

    response = await client.post(
        "/manager/ask",
        headers={"Authorization": f"Bearer {service_token}", "X-On-Behalf-Of-Phone": "+15559991999"},
        json={"message": "hello"},
    )
    assert response.status_code == 403


async def test_ask_ignores_on_behalf_of_header_from_non_service_caller(client):
    """A regular authenticated user cannot impersonate anyone via the header (ADR 0006)."""
    await _link_phone(client, "manageruser-linked2", "+15559991002")
    normal_token = await _login_as(client, "manageruser-normal1")

    with patch(
        "api.manager_agent.chat_completion_with_tools", return_value={"content": "hi there"}
    ) as mock_completion:
        response = await client.post(
            "/manager/ask",
            headers={"Authorization": f"Bearer {normal_token}", "X-On-Behalf-Of-Phone": "+15559991002"},
            json={"message": "hello"},
        )

    assert response.status_code == 200
    called_user_id = mock_completion.call_args.kwargs["user_id"]

    from api.db import async_session
    from api.models import User
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "manageruser-normal1"))
        normal_user = result.scalar_one()
    assert called_user_id == normal_user.id
