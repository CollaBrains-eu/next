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


async def test_draft_includes_preferred_language_in_system_prompt(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    await client.put("/preferences/me", headers=headers, json={"preferred_language": "fr"})

    with (
        patch("api.legal.hybrid_search", return_value=[]),
        patch("api.legal.chat_completion", return_value="ok") as mock_completion,
    ):
        await client.post("/legal/draft", headers=headers, json={"instruction": "Draft an objection."})

    sent_messages = mock_completion.call_args.args[0]
    system_message = sent_messages[0]["content"]
    assert "you must respond only in fr" in system_message.lower()


async def _login_as_legal(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


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
        await client.post("/legal/draft", headers=headers, json={"instruction": "Draft an objection."})

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
            user_id=user.id, fact_type="address", value={"text": "Kerkstraat 1, Amsterdam"},
            valid_from=date(2020, 1, 1), valid_to=None, status="pending_review",
        ))
        await db.commit()

    with (
        patch("api.legal.hybrid_search", return_value=[]),
        patch("api.legal.chat_completion", return_value="ok") as mock_completion,
    ):
        await client.post("/legal/draft", headers=headers, json={"instruction": "Draft an objection."})

    sent_messages = mock_completion.call_args.args[0]
    user_message = sent_messages[-1]["content"]
    assert "Known facts about the user:" not in user_message
