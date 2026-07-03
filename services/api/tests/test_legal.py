from unittest.mock import patch

from sqlalchemy import select

from api.ldap_auth import LdapIdentity
from api.reflection import ReflectionResult


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


async def test_draft_retries_retrieval_when_reflection_flags_insufficient_evidence(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.legal.hybrid_search", side_effect=[[], []]) as mock_hybrid,
        patch("api.legal.chat_completion", side_effect=["first draft", "second draft"]) as mock_completion,
        patch(
            "api.legal.reflect",
            return_value=ReflectionResult(sufficient_evidence=False, confidence=15, issues=["unsupported claim"]),
        ),
    ):
        response = await client.post(
            "/legal/draft", headers=headers, json={"instruction": "Draft an objection.", "context_chunks": 4}
        )

    assert response.status_code == 200
    assert response.json()["draft"] == "second draft"
    assert mock_hybrid.call_count == 2
    assert mock_hybrid.call_args_list[1].kwargs["limit"] == 8  # context_chunks 4, doubled
    assert mock_completion.call_count == 2

    from api.db import async_session
    from api.models import ReflectionLog, User

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == "legaluser"))).scalar_one()
        rows = (
            await db.execute(select(ReflectionLog).where(ReflectionLog.user_id == user.id))
        ).scalars().all()
    assert any(row.retried is True for row in rows)


async def test_draft_does_not_retry_when_reflection_flags_sufficient_evidence(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.legal.hybrid_search", return_value=[]) as mock_hybrid,
        patch("api.legal.chat_completion", return_value="the only draft") as mock_completion,
        patch(
            "api.legal.reflect",
            return_value=ReflectionResult(sufficient_evidence=True, confidence=90, issues=[]),
        ),
    ):
        response = await client.post("/legal/draft", headers=headers, json={"instruction": "Draft an objection."})

    assert response.status_code == 200
    assert response.json()["draft"] == "the only draft"
    assert mock_hybrid.call_count == 1
    assert mock_completion.call_count == 1
