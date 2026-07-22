from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.db import async_session
from api.document_metafields import extract_and_persist_metafields, extract_metafields, is_date_field
from api.models import Document, User

FAKE_INVOICE_METAFIELDS = '{"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123"}'


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_document(owner_id, doc_type: str | None = "invoice") -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="invoice.pdf", filename="invoice.pdf", mime_type="application/pdf",
            status="ready", ocr_text="Invoice #INV-123, total EUR 500.00, due 2026-08-15.", doc_type=doc_type,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def test_extract_metafields_returns_parsed_output_for_known_doc_type():
    user = await _create_user(_unique("metafielduser"))
    with patch("api.document_metafields.chat_completion", AsyncMock(return_value=FAKE_INVOICE_METAFIELDS)):
        result = await extract_metafields(doc_type="invoice", text="Invoice #INV-123.", user_id=user.id)

    assert result == {"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123"}


async def test_extract_metafields_returns_empty_dict_for_doc_type_with_no_schema():
    user = await _create_user(_unique("metafieldnoschemauser"))
    mock = AsyncMock(return_value=FAKE_INVOICE_METAFIELDS)
    with patch("api.document_metafields.chat_completion", mock):
        result = await extract_metafields(doc_type="other", text="whatever", user_id=user.id)

    assert result == {}
    mock.assert_not_called()


async def test_extract_metafields_returns_empty_dict_on_unparseable_output():
    user = await _create_user(_unique("metafieldbaduser"))
    with patch("api.document_metafields.chat_completion", AsyncMock(return_value="not json at all")):
        result = await extract_metafields(doc_type="invoice", text="whatever", user_id=user.id)

    assert result == {}


async def test_extract_metafields_drops_keys_not_in_the_declared_schema():
    user = await _create_user(_unique("metafieldextrauser"))
    fake = '{"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123", "made_up_field": "x"}'
    with patch("api.document_metafields.chat_completion", AsyncMock(return_value=fake)):
        result = await extract_metafields(doc_type="invoice", text="whatever", user_id=user.id)

    assert "made_up_field" not in result


async def test_extract_metafields_requests_the_json_schema_not_bare_json_mode():
    user = await _create_user(_unique("metafieldschemauser"))
    mock = AsyncMock(return_value=FAKE_INVOICE_METAFIELDS)
    with patch("api.document_metafields.chat_completion", mock):
        await extract_metafields(doc_type="invoice", text="whatever", user_id=user.id)

    schema = mock.call_args.kwargs["schema"]
    assert set(schema["properties"]) == {"amount", "due_date", "invoice_number"}


async def test_extract_and_persist_metafields_updates_document():
    user = await _create_user(_unique("metafieldpersistuser"))
    document = await _create_document(user.id, doc_type="invoice")

    with patch("api.document_metafields.chat_completion", AsyncMock(return_value=FAKE_INVOICE_METAFIELDS)):
        async with async_session() as db:
            updated = await extract_and_persist_metafields(
                db, document_id=document.id, doc_type="invoice", text=document.ocr_text, user_id=user.id
            )

    assert updated is not None
    assert updated.metafields == {"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123"}


async def test_extract_and_persist_metafields_leaves_metafields_unset_on_unparseable_output():
    user = await _create_user(_unique("metafieldpersistbaduser"))
    document = await _create_document(user.id, doc_type="invoice")

    with patch("api.document_metafields.chat_completion", AsyncMock(return_value="garbage")):
        async with async_session() as db:
            result = await extract_and_persist_metafields(
                db, document_id=document.id, doc_type="invoice", text=document.ocr_text, user_id=user.id
            )

    assert result is not None
    assert result.metafields is None


async def test_extract_and_persist_metafields_returns_none_for_unknown_document():
    user = await _create_user(_unique("metafieldunknowndocuser"))
    async with async_session() as db:
        result = await extract_and_persist_metafields(
            db, document_id=uuid4(), doc_type="invoice", text="x", user_id=user.id
        )
    assert result is None


def test_is_date_field_identifies_declared_date_fields():
    assert is_date_field("invoice", "due_date") is True
    assert is_date_field("invoice", "amount") is False
    assert is_date_field("invoice", "not_a_real_field") is False
    assert is_date_field("other", "anything") is False
