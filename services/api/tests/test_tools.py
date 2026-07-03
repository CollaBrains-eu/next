from unittest.mock import patch
from uuid import uuid4

import pytest

from api.db import async_session
from api.legal import DraftResponse
from api.models import Document, Entity, Task, User
from api.search_service import SearchHit
from api.tool_registry import dispatch


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_document(owner_id, *, status: str = "ready", ocr_text: str | None = "some text") -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="t", filename="t.pdf", mime_type="application/pdf",
            status=status, ocr_text=ocr_text,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


class _FakeChunk:
    def __init__(self):
        self.id = uuid4()
        self.document_id = uuid4()
        self.content = "hello"


async def test_search_tool_returns_documents():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    fake_hit = SearchHit(chunk=_FakeChunk(), score=0.9)

    with patch("api.tools.hybrid_search", return_value=[fake_hit]):
        result = await dispatch("search", db=None, user_id=user.id, query="hello")

    assert result["documents"][0]["content"] == "hello"
    assert result["documents"][0]["score"] == 0.9


async def test_summarize_document_tool_returns_summary():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    document = await _create_document(user.id)

    async with async_session() as db:
        with patch("api.tools._generate_summary", return_value="a summary"):
            result = await dispatch("summarize_document", db=db, user_id=user.id, document_id=document.id)

    assert result == {"summary": "a summary"}


async def test_summarize_document_tool_rejects_not_ready_document():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    document = await _create_document(user.id, status="pending", ocr_text=None)

    async with async_session() as db:
        with pytest.raises(ValueError):
            await dispatch("summarize_document", db=db, user_id=user.id, document_id=document.id)


async def test_summarize_document_tool_rejects_missing_document():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")

    async with async_session() as db:
        with pytest.raises(ValueError):
            await dispatch("summarize_document", db=db, user_id=user.id, document_id=uuid4())


async def test_draft_legal_document_tool_returns_draft_dict():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    fake_draft = DraftResponse(draft="a draft", citations=[])

    with patch("api.tools._generate_draft", return_value=fake_draft):
        result = await dispatch("draft_legal_document", db=None, user_id=user.id, instruction="draft something")

    assert result["draft"] == "a draft"
    assert "disclaimer" in result


async def test_extract_tasks_tool_returns_tasks():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    document = await _create_document(user.id)
    fake_task = Task(id=uuid4(), title="Do the thing", document_id=document.id)

    with patch("api.tools.extract_tasks", return_value=[fake_task]):
        result = await dispatch(
            "extract_tasks", db=None, user_id=user.id, document_id=document.id, text="do the thing by friday",
        )

    assert result["tasks"][0]["title"] == "Do the thing"


async def test_extract_entities_tool_returns_entities():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    document = await _create_document(user.id)
    fake_entity = Entity(id=uuid4(), name="Jane Doe", entity_type="person")

    with patch("api.tools.extract_entities", return_value=[fake_entity]):
        result = await dispatch(
            "extract_entities", db=None, user_id=user.id, document_id=document.id,
            text="Jane Doe signed the contract",
        )

    assert result["entities"][0]["name"] == "Jane Doe"
