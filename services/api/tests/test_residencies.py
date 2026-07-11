"""Address entities, residency (address-history) detection, and contract
linking. See docs/superpowers/plans/2026-07-11-entity-address-history.md.

Fixtures create Document rows directly via the ORM (not through POST
/documents) so `category_id` and `created_at` are fully controlled --
relocation detection keys off both.

Usernames and street names are both uniqued per test (`_unique`,
`_unique_street`) -- this suite shares one persistent DB with no per-test
rollback, so a fixed username collides across repeated runs, and address
entities dedup *globally* by normalized key (same as every other entity
type, see ADR 0008), so a fixed literal address would let one test's
rejection (`test_rejected_address_entity_is_permanently_suppressed`)
permanently poison that address for every later test in the same run.
"""
import json
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import select

from api.db import async_session
from api.entity_agent import extract_entities
from api.ldap_auth import LdapIdentity
from api.models import AddressDetail, Category, Document, Residency, User


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


def _unique_street() -> str:
    return f"Teststraat-{uuid4().hex[:10]}"


def _address_extraction(
    street: str, house_number: str = "12", postal_code: str = "1012AB", city: str = "Amsterdam",
    formatted_differently: bool = False, extra_entities: list[dict] | None = None,
) -> str:
    s = street.lower() if formatted_differently else street
    p = postal_code.lower() if formatted_differently else postal_code
    entities = list(extra_entities or [])
    entities.append(
        {
            "name": f"{street} {house_number}, {city}", "type": "address", "street": s,
            "house_number": house_number, "postal_code": p, "city": city, "country": "NL",
        }
    )
    return json.dumps({"entities": entities, "relationships": []})


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


async def _create_document(
    owner_id: UUID, *, category_slug: str | None = None, created_at: datetime | None = None
) -> UUID:
    document_id = uuid4()
    category_id = await _category_id(category_slug) if category_slug else None
    async with async_session() as db:
        doc = Document(
            id=document_id, owner_id=owner_id, title="doc", filename="doc.txt", mime_type="text/plain",
            status="ready", category_id=category_id,
        )
        db.add(doc)
        await db.commit()
        if created_at is not None:
            # created_at has a server_default -- set explicitly post-insert if the
            # test needs a specific date for valid_from/valid_to assertions.
            doc_row = await db.get(Document, document_id)
            doc_row.created_at = created_at
            await db.commit()
    return document_id


async def _current_residency(user_id: UUID) -> Residency | None:
    async with async_session() as db:
        result = await db.execute(select(Residency).where(Residency.user_id == user_id, Residency.valid_to.is_(None)))
        return result.scalar_one_or_none()


async def test_extracting_address_from_identity_document_creates_residency(client):
    username = _unique("residencyuser1")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            persisted = await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)

    assert len(persisted) == 1
    assert persisted[0].entity_type == "address"

    residency = await _current_residency(user.id)
    assert residency is not None
    assert residency.status == "pending_review"
    assert residency.address_entity_id == persisted[0].id
    assert residency.source_document_id == document_id


async def test_same_address_seen_twice_is_a_noop(client):
    username = _unique("residencyuser2")
    await _login(client, username)
    user = await _user(username)
    doc_a = await _create_document(user.id, category_slug="identity_document")
    doc_b = await _create_document(user.id, category_slug="rental_contract")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=doc_a, text="id card", user_id=user.id)

    residency_after_first = await _current_residency(user.id)

    async with async_session() as db:
        with patch(
            "api.entity_agent.chat_completion",
            return_value=_address_extraction(street, formatted_differently=True),
        ):
            await extract_entities(db, document_id=doc_b, text="lease", user_id=user.id)

    residency_after_second = await _current_residency(user.id)
    assert residency_after_second is not None
    assert residency_after_second.id == residency_after_first.id
    assert residency_after_second.valid_to is None

    # exactly one address entity should exist -- normalized_key dedup worked
    # across differently-formatted extractions of the same real address
    async with async_session() as db:
        result = await db.execute(select(AddressDetail).where(AddressDetail.street.ilike(street)))
        assert len(result.scalars().all()) == 1


async def test_different_address_closes_old_residency_and_opens_new_one(client):
    username = _unique("residencyuser3")
    await _login(client, username)
    user = await _user(username)
    doc_a = await _create_document(
        user.id, category_slug="identity_document", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    doc_b = await _create_document(
        user.id, category_slug="identity_document", created_at=datetime(2026, 6, 15, tzinfo=timezone.utc)
    )
    old_street, new_street = _unique_street(), _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(old_street)):
            await extract_entities(db, document_id=doc_a, text="id card v1", user_id=user.id)

    async with async_session() as db:
        with patch(
            "api.entity_agent.chat_completion",
            return_value=_address_extraction(new_street, postal_code="3512CD", city="Utrecht"),
        ):
            await extract_entities(db, document_id=doc_b, text="id card v2", user_id=user.id)

    async with async_session() as db:
        result = await db.execute(select(Residency).where(Residency.user_id == user.id).order_by(Residency.valid_from))
        history = list(result.scalars().all())

    assert len(history) == 2
    assert history[0].valid_from.isoformat() == "2026-01-01"
    assert history[0].valid_to.isoformat() == "2026-06-15"
    assert history[1].valid_from.isoformat() == "2026-06-15"
    assert history[1].valid_to is None
    assert history[0].address_entity_id != history[1].address_entity_id


async def test_address_on_non_residence_category_does_not_touch_residency(client):
    """An invoice mentioning a store's address must not be interpreted as
    the user's own residence -- category gating (RESIDENCE_CATEGORY_SLUGS)
    is what prevents this, not the presence of an address entity alone."""
    username = _unique("residencyuser4")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="invoice")
    street = _unique_street()

    async with async_session() as db:
        fake = _address_extraction(
            street, postal_code="3011AA", city="Rotterdam", extra_entities=[{"name": "Mediamarkt", "type": "organization"}]
        )
        with patch("api.entity_agent.chat_completion", return_value=fake):
            persisted = await extract_entities(db, document_id=document_id, text="invoice", user_id=user.id)

    assert any(e.entity_type == "address" for e in persisted)  # address entity still extracted/stored
    assert await _current_residency(user.id) is None  # but no residency created from it


async def test_employment_contract_links_to_existing_current_residency(client):
    """Employment contracts don't themselves reveal a home address
    (RESIDENCE_CATEGORY_SLUGS excludes employment_contract) but should
    still be linked to whatever the user's current residency already is."""
    username = _unique("residencyuser5")
    await _login(client, username)
    user = await _user(username)
    id_doc = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=id_doc, text="id card", user_id=user.id)

    residency = await _current_residency(user.id)
    contract_doc = await _create_document(user.id, category_slug="employment_contract")

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value='{"entities": [], "relationships": []}'):
            await extract_entities(db, document_id=contract_doc, text="contract text", user_id=user.id)

    async with async_session() as db:
        doc = await db.get(Document, contract_doc)
        assert doc.residency_id == residency.id


async def test_list_my_residencies_reports_linked_document_count(client):
    username = _unique("residencyuser11")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    user = await _user(username)
    id_doc = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=id_doc, text="id card", user_id=user.id)

    contract_doc = await _create_document(user.id, category_slug="rental_contract")
    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value='{"entities": [], "relationships": []}'):
            await extract_entities(db, document_id=contract_doc, text="lease text", user_id=user.id)

    response = await client.get("/users/me/residencies", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["linked_document_count"] == 1


async def test_rejected_address_entity_is_permanently_suppressed(client):
    username = _unique("residencyuser6")
    await _login(client, username)
    user = await _user(username)
    doc_a = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            persisted = await extract_entities(db, document_id=doc_a, text="id card", user_id=user.id)

    address_entity_id = persisted[0].id
    async with async_session() as db:
        entity = await db.get(type(persisted[0]), address_entity_id)
        entity.status = "rejected"
        await db.commit()

    doc_b = await _create_document(user.id, category_slug="rental_contract")
    async with async_session() as db:
        with patch(
            "api.entity_agent.chat_completion",
            return_value=_address_extraction(street, formatted_differently=True),
        ):
            persisted_again = await extract_entities(db, document_id=doc_b, text="lease", user_id=user.id)

    assert persisted_again == []  # rejected, permanently suppressed -- matches entity behavior


async def test_list_my_residencies(client):
    username = _unique("residencyuser7")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)

    response = await client.get("/users/me/residencies", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["address"]["postal_code"] == "1012AB"
    assert body[0]["status"] == "pending_review"


async def test_admin_can_list_another_users_residencies_but_member_cannot(client):
    admin_username = _unique("residencyadmin1")
    member_username = _unique("residencymember1")
    admin_token = await _login(client, admin_username, is_admin=True)
    member_token = await _login(client, member_username)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member_headers = {"Authorization": f"Bearer {member_token}"}
    member = await _user(member_username)
    document_id = await _create_document(member.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="id card", user_id=member.id)

    admin_response = await client.get(f"/admin/users/{member.id}/residencies", headers=admin_headers)
    assert admin_response.status_code == 200
    assert len(admin_response.json()) == 1

    forbidden_response = await client.get(f"/admin/users/{member.id}/residencies", headers=member_headers)
    assert forbidden_response.status_code == 403


async def test_approve_and_reject_residency(client):
    username = _unique("residencyuser8")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)

    residency = await _current_residency(user.id)
    response = await client.post(f"/residencies/{residency.id}/approve", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    # already confirmed -- approving again should conflict, matching entity review semantics
    response2 = await client.post(f"/residencies/{residency.id}/approve", headers=headers)
    assert response2.status_code == 409


async def test_correct_residency_dates(client):
    username = _unique("residencyuser9")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)

    residency = await _current_residency(user.id)
    response = await client.patch(
        f"/residencies/{residency.id}", headers=headers, json={"valid_from": "2025-03-01"}
    )
    assert response.status_code == 200
    assert response.json()["valid_from"] == "2025-03-01"


async def test_correct_residency_forbidden_for_other_member(client):
    owner_username = _unique("residencyuser10")
    other_username = _unique("residencymember2")
    await _login(client, owner_username)
    token_other = await _login(client, other_username)
    other_headers = {"Authorization": f"Bearer {token_other}"}
    user = await _user(owner_username)
    document_id = await _create_document(user.id, category_slug="identity_document")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="id card", user_id=user.id)

    residency = await _current_residency(user.id)
    response = await client.patch(
        f"/residencies/{residency.id}", headers=other_headers, json={"valid_from": "2025-03-01"}
    )
    assert response.status_code == 403
