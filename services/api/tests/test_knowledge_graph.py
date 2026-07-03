from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from api.db import async_session
from api.knowledge_graph import create_decision_from_plan, get_decision_with_documents
from api.models import Document, GraphEdge, User
from api.planning_engine import approve_plan, create_plan


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_document(owner_id) -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="Evidence letter", filename="t.pdf", mime_type="application/pdf",
            status="ready", ocr_text="some text",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def test_create_decision_from_plan_links_referenced_documents():
    user = await _create_user(_unique("kguser"))
    document = await _create_document(user.id)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=user.id, goal_type="draft_legal_document",
            goal_params={"instruction": "Draft a notice.", "document_ids": [str(document.id)]},
        )
        decision = await create_decision_from_plan(db, plan=plan, user_id=user.id)

    assert decision.plan_id == plan.id
    assert decision.user_id == user.id

    async with async_session() as db:
        edges = (
            await db.execute(select(GraphEdge).where(GraphEdge.source_id == decision.id))
        ).scalars().all()
    assert len(edges) == 1
    assert edges[0].target_id == document.id
    assert edges[0].relationship_type == "derived_from"


async def test_create_decision_from_plan_with_no_documents_creates_no_edges():
    user = await _create_user(_unique("kguser"))

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=user.id, goal_type="draft_legal_document", goal_params={"instruction": "Draft a notice."},
        )
        decision = await create_decision_from_plan(db, plan=plan, user_id=user.id)

    async with async_session() as db:
        result = await get_decision_with_documents(db, decision.id)

    assert result is not None
    _, documents = result
    assert documents == []


async def test_get_decision_with_documents_returns_none_for_unknown_id():
    async with async_session() as db:
        result = await get_decision_with_documents(db, uuid4())
    assert result is None


async def test_get_decision_with_documents_returns_linked_documents():
    user = await _create_user(_unique("kguser"))
    document = await _create_document(user.id)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=user.id, goal_type="draft_legal_document",
            goal_params={"instruction": "Draft a notice.", "document_ids": [str(document.id)]},
        )
        decision = await create_decision_from_plan(db, plan=plan, user_id=user.id)

    async with async_session() as db:
        result = await get_decision_with_documents(db, decision.id)

    assert result is not None
    fetched_decision, documents = result
    assert fetched_decision.id == decision.id
    assert [doc.id for doc in documents] == [document.id]


async def test_approve_plan_creates_a_decision_linked_to_its_documents():
    user = await _create_user(_unique("kguser"))
    document = await _create_document(user.id)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=user.id, goal_type="draft_legal_document",
            goal_params={"instruction": "Draft a notice.", "document_ids": [str(document.id)]},
        )

    with (
        patch("api.legal.hybrid_search", return_value=[]),
        patch("api.legal.chat_completion", return_value="Draft text."),
    ):
        async with async_session() as db:
            await approve_plan(db, plan_id=plan.id, user_id=user.id)

    async with async_session() as db:
        edges = (
            await db.execute(
                select(GraphEdge).where(GraphEdge.source_type == "decision", GraphEdge.target_id == document.id)
            )
        ).scalars().all()
    assert len(edges) == 1
