from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from api.db import async_session
from api.models import ReflectionLog, User
from api.reflection import REFLECTION_SCHEMA, ReflectionResult, log_reflection, reflect


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def test_reflect_parses_well_formed_json():
    user = await _create_user(f"reflect-user-{uuid4().hex[:8]}")

    with patch(
        "api.reflection.chat_completion",
        return_value='{"sufficient_evidence": false, "confidence": 30, "issues": ["no supporting excerpt"]}',
    ) as mock_completion:
        result = await reflect(
            question="What is the deadline?", answer="The deadline is next Friday.",
            context_text="(no relevant documents found)", user_id=user.id, endpoint="chat",
        )

    assert result.sufficient_evidence is False
    assert result.confidence == 30
    assert result.issues == ["no supporting excerpt"]
    assert mock_completion.call_args.kwargs["schema"] == REFLECTION_SCHEMA


async def test_reflect_falls_back_permissively_on_malformed_json():
    user = await _create_user(f"reflect-user-{uuid4().hex[:8]}")

    with patch("api.reflection.chat_completion", return_value="not json at all"):
        result = await reflect(
            question="q", answer="a", context_text="c", user_id=user.id, endpoint="chat",
        )

    assert result.sufficient_evidence is True
    assert result.confidence == 100
    assert result.issues == []


async def test_reflect_clamps_out_of_range_confidence():
    user = await _create_user(f"reflect-user-{uuid4().hex[:8]}")

    with patch(
        "api.reflection.chat_completion",
        return_value='{"sufficient_evidence": true, "confidence": 500, "issues": []}',
    ):
        result = await reflect(
            question="q", answer="a", context_text="c", user_id=user.id, endpoint="chat",
        )

    assert result.confidence == 100


async def test_reflect_ignores_non_string_issues():
    user = await _create_user(f"reflect-user-{uuid4().hex[:8]}")

    with patch(
        "api.reflection.chat_completion",
        return_value='{"sufficient_evidence": true, "confidence": 80, "issues": [1, 2]}',
    ):
        result = await reflect(
            question="q", answer="a", context_text="c", user_id=user.id, endpoint="chat",
        )

    assert result.issues == []


async def test_log_reflection_persists_a_row():
    user = await _create_user(f"reflect-user-{uuid4().hex[:8]}")
    result = ReflectionResult(sufficient_evidence=False, confidence=42, issues=["missing evidence"])

    async with async_session() as db:
        await log_reflection(
            db, user_id=user.id, endpoint="chat", question="What is the deadline?",
            result=result, retried=True,
        )

    async with async_session() as db:
        rows = (await db.execute(select(ReflectionLog).where(ReflectionLog.user_id == user.id))).scalars().all()

    assert len(rows) == 1
    row = rows[0]
    assert row.endpoint == "chat"
    assert row.sufficient_evidence is False
    assert row.confidence == 42
    assert row.issues == ["missing evidence"]
    assert row.retried is True
