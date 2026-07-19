from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.db import async_session
from api.document_classification import CLASSIFICATION_SCHEMA, classify_and_persist, classify_document
from api.models import Document, User

FAKE_CLASSIFICATION = (
    '{"doc_type": "invoice", "tags": ["btw", "q3"], "correspondent": "Acme BV", "confidence": 0.87}'
)


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
            owner_id=owner_id, title="invoice.pdf", filename="invoice.pdf", mime_type="application/pdf",
            status="ready", ocr_text="Invoice #123 from Acme BV, total EUR 500 excl. BTW.",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def test_classify_document_returns_valid_parsed_output():
    user = await _create_user(_unique("classifyuser"))
    with patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_CLASSIFICATION)):
        result = await classify_document(text="Invoice #123 from Acme BV.", user_id=user.id)

    assert result is not None
    assert result.doc_type == "invoice"
    assert result.tags == ["btw", "q3"]
    assert result.correspondent == "Acme BV"
    assert result.confidence == 0.87


async def test_classify_document_requests_the_json_schema_not_bare_json_mode():
    user = await _create_user(_unique("classifyschemauser"))
    mock = AsyncMock(return_value=FAKE_CLASSIFICATION)
    with patch("api.document_classification.chat_completion", mock):
        await classify_document(text="Invoice #123 from Acme BV.", user_id=user.id)

    assert mock.call_args.kwargs["schema"] == CLASSIFICATION_SCHEMA


async def test_classify_document_returns_none_on_unparseable_output():
    user = await _create_user(_unique("classifybaduser"))
    with patch("api.document_classification.chat_completion", AsyncMock(return_value="not json at all")):
        result = await classify_document(text="whatever", user_id=user.id)

    assert result is None


async def test_classify_document_defaults_unknown_doc_type_to_other():
    user = await _create_user(_unique("classifyunknownuser"))
    fake = '{"doc_type": "not-a-real-type", "tags": [], "correspondent": null, "confidence": 0.5}'
    with patch("api.document_classification.chat_completion", AsyncMock(return_value=fake)):
        result = await classify_document(text="whatever", user_id=user.id)

    assert result is not None
    assert result.doc_type == "other"


async def test_classify_document_clamps_tags_to_five():
    user = await _create_user(_unique("classifytagsuser"))
    fake = '{"doc_type": "other", "tags": ["a", "b", "c", "d", "e", "f", "g"], "correspondent": null, "confidence": 0.1}'
    with patch("api.document_classification.chat_completion", AsyncMock(return_value=fake)):
        result = await classify_document(text="whatever", user_id=user.id)

    assert result is not None
    assert len(result.tags) == 5


async def test_classify_and_persist_updates_document_fields():
    user = await _create_user(_unique("classifypersistuser"))
    document = await _create_document(user.id)

    with patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_CLASSIFICATION)):
        async with async_session() as db:
            updated = await classify_and_persist(
                db, document_id=document.id, text=document.ocr_text, user_id=user.id
            )

    assert updated is not None
    assert updated.doc_type == "invoice"
    assert updated.correspondent == "Acme BV"
    assert updated.classification_confidence == 0.87


async def test_classify_and_persist_leaves_document_unchanged_on_unparseable_output():
    user = await _create_user(_unique("classifypersistbaduser"))
    document = await _create_document(user.id)

    with patch("api.document_classification.chat_completion", AsyncMock(return_value="garbage")):
        async with async_session() as db:
            result = await classify_and_persist(
                db, document_id=document.id, text=document.ocr_text, user_id=user.id
            )

    assert result is not None
    assert result.doc_type is None


async def test_classify_and_persist_returns_none_for_unknown_document():
    user = await _create_user(_unique("classifyunknowndocuser"))
    async with async_session() as db:
        result = await classify_and_persist(db, document_id=uuid4(), text="x", user_id=user.id)
    assert result is None


async def test_classify_document_accepts_the_full_expanded_taxonomy():
    user = await _create_user(_unique("classifyrichuser"))
    fake = '{"doc_type": "payslip", "tags": [], "correspondent": null, "confidence": 0.9}'
    with patch("api.document_classification.chat_completion", AsyncMock(return_value=fake)):
        result = await classify_document(text="whatever", user_id=user.id)

    assert result is not None
    assert result.doc_type == "payslip"


async def test_classify_and_persist_sets_category_from_doc_type():
    from sqlalchemy import select
    from api.models import Category

    user = await _create_user(_unique("classifycatuser"))
    document = await _create_document(user.id)
    fake = '{"doc_type": "payslip", "tags": [], "correspondent": null, "confidence": 0.9}'

    with patch("api.document_classification.chat_completion", AsyncMock(return_value=fake)):
        async with async_session() as db:
            updated = await classify_and_persist(
                db, document_id=document.id, text=document.ocr_text, user_id=user.id
            )

    assert updated is not None
    assert updated.category_id is not None

    async with async_session() as db:
        category = (
            await db.execute(select(Category).where(Category.id == updated.category_id))
        ).scalar_one()
    assert category.slug == "payslip"


async def test_classify_and_persist_falls_back_to_other_documents_category_for_unmapped_doc_type():
    from sqlalchemy import select
    from api.models import Category

    user = await _create_user(_unique("classifyfallbackuser"))
    document = await _create_document(user.id)
    fake = '{"doc_type": "other", "tags": [], "correspondent": null, "confidence": 0.2}'

    with patch("api.document_classification.chat_completion", AsyncMock(return_value=fake)):
        async with async_session() as db:
            updated = await classify_and_persist(
                db, document_id=document.id, text=document.ocr_text, user_id=user.id
            )

    async with async_session() as db:
        category = (
            await db.execute(select(Category).where(Category.id == updated.category_id))
        ).scalar_one()
    assert category.slug == "other_documents"
