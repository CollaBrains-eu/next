from unittest.mock import patch

from api.ldap_auth import LdapIdentity


async def _login(client) -> str:
    identity = LdapIdentity(
        username="legaluser", display_name="Legal User", email="legaluser@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "legaluser", "password": "whatever"})
    return response.json()["access_token"]


async def test_draft_returns_disclaimer_and_citations(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.legal.hybrid_search", return_value=[]),
        patch("api.legal.chat_completion", return_value="I don't have enough context to draft this."),
    ):
        response = await client.post(
            "/legal/draft", headers=headers, json={"instruction": "Draft an objection to the motion."}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["draft"] == "I don't have enough context to draft this."
    assert body["citations"] == []
    assert "not legal advice" in body["disclaimer"]


async def test_draft_rejects_missing_token(client):
    response = await client.post("/legal/draft", json={"instruction": "Draft anything."})
    assert response.status_code == 401
