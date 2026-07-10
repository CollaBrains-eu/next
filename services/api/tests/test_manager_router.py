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
        "content": "",
        "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hello"}}}],
    }

    with (
        patch("api.manager_agent.chat_completion_with_tools", return_value=tool_call_response),
        patch("api.tools.hybrid_search", return_value=[fake_hit]),
        patch("api.manager_agent.chat_completion", return_value="Found it."),
    ):
        response = await client.post("/manager/ask", headers=headers, json={"message": "find hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Found it."
    assert body["tools_called"] == ["search"]


async def test_ask_rejects_missing_token(client):
    response = await client.post("/manager/ask", json={"message": "hello"})
    assert response.status_code == 401
