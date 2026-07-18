from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import AnswerFeedback


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_submit_feedback_requires_auth(client):
    response = await client.post(
        "/feedback",
        json={"endpoint": "chat", "question": "q", "answer": "a", "rating": "up"},
    )
    assert response.status_code == 401


async def test_submit_feedback_persists_a_row_with_the_correct_fields(client):
    username = _unique("feedbackuser")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    question = _unique("What is the retention policy?")

    response = await client.post(
        "/feedback",
        headers=headers,
        json={
            "endpoint": "chat",
            "question": question,
            "answer": "Documents are retained for 7 years.",
            "rating": "down",
            "reflection_confidence": 85,
            "reflection_sufficient_evidence": True,
        },
    )
    assert response.status_code == 201

    async with async_session() as db:
        result = await db.execute(select(AnswerFeedback).where(AnswerFeedback.question == question))
        row = result.scalar_one()

    assert row.answer == "Documents are retained for 7 years."
    assert row.rating == "down"
    assert row.endpoint == "chat"
    assert row.reflection_confidence == 85
    assert row.reflection_sufficient_evidence is True
    assert row.user_id is not None


async def test_submit_feedback_rejects_invalid_rating(client):
    token = await _login(client, _unique("feedbackbadrating"))
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/feedback",
        headers=headers,
        json={"endpoint": "chat", "question": "q", "answer": "a", "rating": "sideways"},
    )
    assert response.status_code == 422
