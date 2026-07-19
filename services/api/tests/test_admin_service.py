from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from api.admin_service import (
    CLARIFY_SCHEMA,
    analyze_bug_report,
    create_bug_report,
    generate_clarifying_questions,
    get_admin_stats,
    get_ai_usage_report,
    get_service_health,
    list_bug_reports,
)
from api.db import async_session
from api.models import AiCallLog, Document, User


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str, *, role: str = "member") -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role=role)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_document(owner_id) -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="t", filename="f.pdf", mime_type="application/pdf", status="ready",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def _create_ai_call_log(user_id, *, endpoint: str = "chat", model: str = "qwen2.5:3b-instruct") -> None:
    async with async_session() as db:
        db.add(AiCallLog(user_id=user_id, endpoint=endpoint, model=model, duration_ms=10))
        await db.commit()


async def test_get_admin_stats_counts_users_and_documents_by_status():
    user = await _create_user(_unique("statsuser"))
    await _create_document(user.id)

    async with async_session() as db:
        stats = await get_admin_stats(db)

    assert stats.total_users >= 1
    assert stats.total_documents >= 1
    assert stats.documents_by_status.get("ready", 0) >= 1


async def test_get_admin_stats_counts_recent_ai_calls():
    user = await _create_user(_unique("statsaiuser"))
    await _create_ai_call_log(user.id)

    async with async_session() as db:
        stats = await get_admin_stats(db)

    assert stats.ai_calls_last_24h >= 1


async def test_get_ai_usage_report_groups_by_model():
    user = await _create_user(_unique("usageuser"))
    model_name = _unique("unique-test-model")
    await _create_ai_call_log(user.id, model=model_name)

    async with async_session() as db:
        rows = await get_ai_usage_report(db, since=datetime.utcnow() - timedelta(hours=1), group_by="model")

    matching = [row for row in rows if row.key == model_name]
    assert len(matching) == 1
    assert matching[0].call_count == 1


async def test_get_ai_usage_report_excludes_calls_before_since():
    user = await _create_user(_unique("usageolduser"))
    async with async_session() as db:
        old = AiCallLog(
            user_id=user.id, endpoint="chat", model="old-model-excluded", duration_ms=10,
            created_at=datetime.utcnow() - timedelta(days=30),
        )
        db.add(old)
        await db.commit()

    async with async_session() as db:
        rows = await get_ai_usage_report(db, since=datetime.utcnow() - timedelta(hours=1), group_by="model")

    assert not any(row.key == "old-model-excluded" for row in rows)


async def test_get_service_health_reports_postgres_up():
    async with async_session() as db:
        results = await get_service_health(db)

    postgres = next(r for r in results if r.name == "postgres")
    assert postgres.status == "up"


async def test_get_service_health_reports_down_on_connection_error():
    async with async_session() as db:
        with patch("api.admin_service.httpx.AsyncClient.get", AsyncMock(side_effect=httpx.ConnectError("boom"))):
            results = await get_service_health(db)

    paperless = next(r for r in results if r.name == "paperless")
    assert paperless.status == "down"


async def test_create_and_list_bug_reports():
    user = await _create_user(_unique("buguser"))
    async with async_session() as db:
        created = await create_bug_report(db, user_id=user.id, description="things are broken")

    async with async_session() as db:
        reports = await list_bug_reports(db, status="open")

    assert any(r.id == created.id for r in reports)
    assert created.status == "open"
    assert created.ai_analysis is None


async def test_analyze_bug_report_sets_analysis_and_status():
    user = await _create_user(_unique("buganalyzeuser"))
    async with async_session() as db:
        created = await create_bug_report(db, user_id=user.id, description="upload fails silently")

    with patch("api.admin_service.chat_completion", AsyncMock(return_value="Likely an upload timeout, medium severity.")):
        async with async_session() as db:
            analyzed = await analyze_bug_report(db, bug_report_id=created.id, requesting_user_id=user.id)

    assert analyzed is not None
    assert analyzed.status == "analyzed"
    assert "timeout" in analyzed.ai_analysis


async def test_analyze_bug_report_returns_none_for_unknown_id():
    async with async_session() as db:
        result = await analyze_bug_report(db, bug_report_id=uuid4(), requesting_user_id=uuid4())
    assert result is None


async def test_generate_clarifying_questions_requests_the_json_schema():
    user = await _create_user(_unique("bugclarifyuser"))
    async with async_session() as db:
        created = await create_bug_report(db, user_id=user.id, description="things are broken sometimes")

    with patch(
        "api.admin_service.chat_completion", AsyncMock(return_value='{"questions": ["Which page?"]}')
    ) as mock_completion:
        async with async_session() as db:
            result = await generate_clarifying_questions(db, bug_report_id=created.id, requesting_user_id=user.id)

    assert result is not None
    assert result[1] == ["Which page?"]
    assert mock_completion.call_args.kwargs["schema"] == CLARIFY_SCHEMA
