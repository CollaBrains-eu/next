"""Tests for the residency/address-detection catch-up path.

`extract_entities` (entity_agent.py) gates residency detection on
`Document.category_id`, but entity extraction is dispatched *before*
classification for every `EmbeddingsCreated` event (see documents.py's
subscriber registration order) -- so `category_id` is normally still NULL
when that gate is checked, and classification can also fail transiently on
its own under Ollama load. Either way, residency detection can be silently
skipped on the first pass with nothing to retry it.

`reconcile_residency_for_document` and the admin `backfill_residency_detection`
below are the catch-up paths that make the data eventually consistent once
`category_id` is actually known. See entity_agent.py's module docstring for
the full story, and test_document_classification_events.py for the
end-to-end regression test that exercises the real event ordering.
"""
import json
from unittest.mock import patch
from uuid import UUID, uuid4

from api.admin_service import backfill_residency_detection
from api.db import async_session
from api.entity_agent import extract_entities, reconcile_residency_for_document
from api.ldap_auth import LdapIdentity
from api.models import Category, Document, Residency, User
from sqlalchemy import select


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


def _unique_street() -> str:
    return f"Reconcilestraat-{uuid4().hex[:10]}"


def _address_extraction(
    street: str, house_number: str = "12", postal_code: str = "1012AB", city: str = "Amsterdam"
) -> str:
    return json.dumps(
        {
            "entities": [
                {
                    "name": f"{street} {house_number}, {city}", "type": "address", "street": street,
                    "house_number": house_number, "postal_code": postal_code, "city": city, "country": "NL",
                }
            ],
            "relationships": [],
        }
    )


async def _login(client, username: str, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user(username: str) -> User:
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one()


async def _category_id(slug: str) -> UUID:
    async with async_session() as db:
        result = await db.execute(select(Category).where(Category.slug == slug))
        return result.scalar_one().id


async def _create_document(owner_id: UUID, *, category_slug: str | None = None) -> UUID:
    document_id = uuid4()
    category_id = await _category_id(category_slug) if category_slug else None
    async with async_session() as db:
        doc = Document(
            id=document_id, owner_id=owner_id, title="doc", filename="doc.txt", mime_type="text/plain",
            status="ready", category_id=category_id,
        )
        db.add(doc)
        await db.commit()
    return document_id


async def _set_category(document_id: UUID, category_slug: str) -> None:
    category_id = await _category_id(category_slug)
    async with async_session() as db:
        doc = await db.get(Document, document_id)
        doc.category_id = category_id
        await db.commit()


async def _current_residency(user_id: UUID) -> Residency | None:
    async with async_session() as db:
        result = await db.execute(select(Residency).where(Residency.user_id == user_id, Residency.valid_to.is_(None)))
        return result.scalar_one_or_none()


async def test_reconcile_is_noop_when_category_still_null(client):
    username = _unique("reconcilenocat")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug=None)
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            persisted = await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)
    assert persisted  # address entity was extracted and mentioned on the document
    assert await _current_residency(user.id) is None  # gated on category, still unknown

    async with async_session() as db:
        await reconcile_residency_for_document(db, document_id=document_id)

    assert await _current_residency(user.id) is None  # nothing to reconcile yet


async def test_reconcile_creates_residency_once_category_becomes_known(client):
    """The core regression scenario: extraction ran while `category_id` was
    still NULL (the normal case per entity_agent.py's docstring, not just a
    failure edge case) -- residency detection must have a path to catch up
    once classification later sets `category_id`, without a fresh
    extraction pass."""
    username = _unique("reconcilelate")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug=None)
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            persisted = await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)
    assert await _current_residency(user.id) is None

    # Classification "succeeds later" -- same effect classify_and_persist has
    # on category_id, without needing a real AI call in this test.
    await _set_category(document_id, "identity_document")

    async with async_session() as db:
        await reconcile_residency_for_document(db, document_id=document_id)

    residency = await _current_residency(user.id)
    assert residency is not None
    assert residency.address_entity_id == persisted[0].id
    assert residency.source_document_id == document_id


async def test_reconcile_is_idempotent(client):
    username = _unique("reconcileidem")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)

    residency_after_extraction = await _current_residency(user.id)
    assert residency_after_extraction is not None

    # Calling reconcile again (e.g. DOCUMENT_CLASSIFIED firing a second time
    # on a reprocess, or an admin backfill re-run) must not open a second
    # residency period for the same address.
    async with async_session() as db:
        await reconcile_residency_for_document(db, document_id=document_id)
    async with async_session() as db:
        await reconcile_residency_for_document(db, document_id=document_id)

    async with async_session() as db:
        result = await db.execute(select(Residency).where(Residency.user_id == user.id))
        all_residencies = result.scalars().all()
    assert len(all_residencies) == 1
    assert all_residencies[0].id == residency_after_extraction.id


async def test_reconcile_links_contract_document_once_category_known(client):
    """`_maybe_link_contract` gates on `category_slug` the same way residency
    detection does -- the catch-up path must cover it too, not just new
    `Residency` rows."""
    username = _unique("reconcilecontract")
    await _login(client, username)
    user = await _user(username)
    id_doc = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()
    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=id_doc, text="id card", user_id=user.id)
    residency = await _current_residency(user.id)
    assert residency is not None

    contract_doc = await _create_document(user.id, category_slug=None)
    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value='{"entities": [], "relationships": []}'):
            await extract_entities(db, document_id=contract_doc, text="contract text", user_id=user.id)

    async with async_session() as db:
        doc = await db.get(Document, contract_doc)
        assert doc.residency_id is None  # category still unknown at extraction time

    await _set_category(contract_doc, "employment_contract")

    async with async_session() as db:
        await reconcile_residency_for_document(db, document_id=contract_doc)

    async with async_session() as db:
        doc = await db.get(Document, contract_doc)
        assert doc.residency_id == residency.id


async def test_backfill_residency_detection_reconciles_orphaned_documents(client):
    """admin_service.backfill_residency_detection: the on-demand catch-up for
    documents that had residency detection silently skipped with no
    DOCUMENT_CLASSIFIED-triggered reconcile ever firing for them (e.g.
    because they were processed before this fix shipped)."""
    username = _unique("backfilluser")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug=None)
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)
    assert await _current_residency(user.id) is None

    await _set_category(document_id, "identity_document")

    async with async_session() as db:
        scanned = await backfill_residency_detection(db)

    assert scanned >= 1
    residency = await _current_residency(user.id)
    assert residency is not None


async def test_backfill_residency_detection_is_safe_to_run_twice(client):
    username = _unique("backfilltwice")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)

    residency = await _current_residency(user.id)
    assert residency is not None

    async with async_session() as db:
        await backfill_residency_detection(db)
    async with async_session() as db:
        await backfill_residency_detection(db)

    async with async_session() as db:
        result = await db.execute(select(Residency).where(Residency.user_id == user.id))
        all_residencies = result.scalars().all()
    assert len(all_residencies) == 1
    assert all_residencies[0].id == residency.id


async def test_backfill_residency_detection_endpoint_requires_admin(client):
    username = _unique("backfillmember")
    token = await _login(client, username)
    response = await client.post(
        "/admin/documents/backfill-residency", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_backfill_residency_detection_endpoint_returns_scanned_count(client):
    username = _unique("backfillendpoint")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug=None)
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)
    await _set_category(document_id, "identity_document")

    admin_token = await _login(client, _unique("backfillendpointadmin"), is_admin=True)
    response = await client.post(
        "/admin/documents/backfill-residency", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["documents_scanned"] >= 1
    assert (await _current_residency(user.id)) is not None
