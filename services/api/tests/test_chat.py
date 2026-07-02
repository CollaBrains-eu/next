from unittest.mock import patch

from api.ldap_auth import LdapIdentity


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
