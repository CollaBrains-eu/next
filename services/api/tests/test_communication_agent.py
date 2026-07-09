from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from api.communication_agent import draft_communication
from api.db import async_session
from api.models import DocumentChunk
from api.search_service import SearchHit


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


def _fake_hit(content: str) -> SearchHit:
    chunk = DocumentChunk(
        id=uuid4(), document_id=uuid4(), chunk_index=0, content=content, embedding=[0.0] * 768,
    )
    return SearchHit(chunk=chunk, score=1.0)


async def test_draft_communication_rejects_unknown_channel():
    async with async_session() as db:
        with pytest.raises(ValueError):
            await draft_communication(
                db, instruction="x", channel="carrier-pigeon", recipient="y", user_id=uuid4(),
            )


async def test_draft_communication_grounds_prompt_in_retrieved_context_only():
    fake_reply = '{"subject": null, "body": "Reminder: your APK expires on 2026-08-01."}'
    hit = _fake_hit("Vehicle APK expiry date: 2026-08-01.")

    with (
        patch("api.communication_agent.hybrid_search", AsyncMock(return_value=[hit])) as mock_search,
        patch("api.communication_agent.chat_completion", AsyncMock(return_value=fake_reply)) as mock_completion,
    ):
        async with async_session() as db:
            draft = await draft_communication(
                db, instruction="Remind about APK expiry", channel="signal", recipient="+31600000000",
                user_id=uuid4(),
            )

    assert draft.channel == "signal"
    assert draft.subject is None
    assert "2026-08-01" in draft.body
    mock_search.assert_awaited_once()
    # The retrieved chunk content must be part of what the model saw.
    sent_messages = mock_completion.call_args.args[0]
    assert any("APK expiry date" in m["content"] for m in sent_messages)


async def test_draft_communication_reports_insufficient_context_when_nothing_found():
    with (
        patch("api.communication_agent.hybrid_search", AsyncMock(return_value=[])),
        patch(
            "api.communication_agent.chat_completion",
            AsyncMock(return_value='{"subject": null, "body": "I do not have enough information to draft this."}'),
        ) as mock_completion,
    ):
        async with async_session() as db:
            draft = await draft_communication(
                db, instruction="Tell them about the meeting", channel="signal", recipient="+31600000001",
                user_id=uuid4(),
            )

    sent_messages = mock_completion.call_args.args[0]
    assert "no relevant documents found" in sent_messages[1]["content"]
    assert "enough information" in draft.body


async def test_draft_communication_falls_back_to_raw_text_on_unparseable_output():
    with (
        patch("api.communication_agent.hybrid_search", AsyncMock(return_value=[])),
        patch("api.communication_agent.chat_completion", AsyncMock(return_value="not json")),
    ):
        async with async_session() as db:
            draft = await draft_communication(
                db, instruction="x", channel="email", recipient="a@example.com", user_id=uuid4(),
            )

    assert draft.body == "not json"
    assert draft.subject is None


async def test_draft_communication_scopes_search_to_given_document_ids():
    scoped_id = uuid4()
    with (
        patch("api.communication_agent.hybrid_search", AsyncMock(return_value=[])) as mock_search,
        patch("api.communication_agent.chat_completion", AsyncMock(return_value='{"subject": null, "body": "ok"}')),
    ):
        async with async_session() as db:
            await draft_communication(
                db, instruction="x", channel="signal", recipient="y", user_id=uuid4(),
                document_ids=[scoped_id],
            )

    assert mock_search.call_args.kwargs["document_ids"] == {scoped_id}
