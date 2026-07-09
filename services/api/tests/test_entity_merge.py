from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from api.db import async_session
from api.entities import merge_entities
from api.ldap_auth import LdapIdentity
from api.models import Document, Entity, EntityMention, EntityMergeLog, EntityRelationship, User


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
        document = Document(owner_id=owner_id, title="t", filename="f.pdf", mime_type="application/pdf")
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def _create_entity(name: str, entity_type: str = "organization", status: str = "confirmed") -> Entity:
    async with async_session() as db:
        entity = Entity(name=name, entity_type=entity_type, status=status)
        db.add(entity)
        await db.commit()
        await db.refresh(entity)
        return entity


async def test_merge_moves_mention_to_target():
    user = await _create_user(_unique("mergeuser"))
    doc = await _create_document(user.id)
    target = await _create_entity(_unique("Acme Corporation"))
    source = await _create_entity(_unique("Acme Corp"))

    async with async_session() as db:
        db.add(EntityMention(entity_id=source.id, document_id=doc.id))
        await db.commit()

    async with async_session() as db:
        result = await merge_entities(db, target_id=target.id, source_id=source.id, merged_by=user.id)

    assert result.id == target.id

    async with async_session() as db:
        mentions = (await db.execute(select(EntityMention).where(EntityMention.entity_id == target.id))).scalars().all()
    assert len(mentions) == 1
    assert mentions[0].document_id == doc.id


async def test_merge_drops_duplicate_mention_for_same_document():
    user = await _create_user(_unique("mergedupuser"))
    doc = await _create_document(user.id)
    target = await _create_entity(_unique("Acme Corporation"))
    source = await _create_entity(_unique("Acme Corp"))

    async with async_session() as db:
        db.add(EntityMention(entity_id=target.id, document_id=doc.id))
        db.add(EntityMention(entity_id=source.id, document_id=doc.id))
        await db.commit()

    async with async_session() as db:
        await merge_entities(db, target_id=target.id, source_id=source.id, merged_by=user.id)

    async with async_session() as db:
        mentions = (
            await db.execute(select(EntityMention).where(EntityMention.document_id == doc.id))
        ).scalars().all()
    assert len(mentions) == 1
    assert mentions[0].entity_id == target.id


async def test_merge_repoints_relationship_to_target():
    user = await _create_user(_unique("mergereluser"))
    target = await _create_entity(_unique("Acme Corporation"))
    source = await _create_entity(_unique("Acme Corp"))
    other = await _create_entity(_unique("Jane Doe"), entity_type="person")

    async with async_session() as db:
        db.add(EntityRelationship(source_entity_id=other.id, target_entity_id=source.id, relationship_type="works_at"))
        await db.commit()

    async with async_session() as db:
        await merge_entities(db, target_id=target.id, source_id=source.id, merged_by=user.id)

    async with async_session() as db:
        rels = (
            await db.execute(select(EntityRelationship).where(EntityRelationship.source_entity_id == other.id))
        ).scalars().all()
    assert len(rels) == 1
    assert rels[0].target_entity_id == target.id


async def test_merge_drops_relationship_that_would_become_a_self_loop():
    user = await _create_user(_unique("mergeselfloopuser"))
    target = await _create_entity(_unique("Acme Corporation"))
    source = await _create_entity(_unique("Acme Corp"))

    async with async_session() as db:
        db.add(EntityRelationship(source_entity_id=target.id, target_entity_id=source.id, relationship_type="alias_of"))
        await db.commit()

    async with async_session() as db:
        await merge_entities(db, target_id=target.id, source_id=source.id, merged_by=user.id)

    async with async_session() as db:
        rels = (
            await db.execute(
                select(EntityRelationship).where(
                    (EntityRelationship.source_entity_id == target.id)
                    | (EntityRelationship.target_entity_id == target.id)
                )
            )
        ).scalars().all()
    assert all(r.source_entity_id != r.target_entity_id for r in rels)


async def test_merge_deletes_source_entity():
    user = await _create_user(_unique("mergedeleteuser"))
    target = await _create_entity(_unique("Acme Corporation"))
    source = await _create_entity(_unique("Acme Corp"))

    async with async_session() as db:
        await merge_entities(db, target_id=target.id, source_id=source.id, merged_by=user.id)

    async with async_session() as db:
        assert await db.get(Entity, source.id) is None
        assert await db.get(Entity, target.id) is not None


async def test_merge_logged_in_entity_merge_log():
    user = await _create_user(_unique("mergeloguser"))
    target = await _create_entity(_unique("Acme Corporation"))
    source = await _create_entity(_unique("Acme Corp"))

    async with async_session() as db:
        await merge_entities(db, target_id=target.id, source_id=source.id, merged_by=user.id)

    async with async_session() as db:
        logs = (
            await db.execute(select(EntityMergeLog).where(EntityMergeLog.target_entity_id == target.id))
        ).scalars().all()
    assert len(logs) == 1
    assert logs[0].source_entity_id == source.id
    assert logs[0].merged_by == user.id


async def test_merge_raises_for_unknown_target():
    user = await _create_user(_unique("mergeunknownuser"))
    source = await _create_entity(_unique("Acme Corp"))

    async with async_session() as db:
        with pytest.raises(ValueError):
            await merge_entities(db, target_id=uuid4(), source_id=source.id, merged_by=user.id)


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_merge_endpoint_rejects_merging_entity_into_itself(client):
    token = await _login(client, _unique("mergeselfuser"))
    target = await _create_entity(_unique("Acme Corporation"))

    response = await client.post(
        f"/entities/{target.id}/merge",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_entity_id": str(target.id)},
    )
    assert response.status_code == 400


async def test_merge_endpoint_returns_404_for_unknown_source(client):
    token = await _login(client, _unique("merge404user"))
    target = await _create_entity(_unique("Acme Corporation"))

    response = await client.post(
        f"/entities/{target.id}/merge",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_entity_id": str(uuid4())},
    )
    assert response.status_code == 404


async def test_merge_endpoint_returns_merged_entity(client):
    token = await _login(client, _unique("mergeendpointuser"))
    target = await _create_entity(_unique("Acme Corporation"))
    source = await _create_entity(_unique("Acme Corp"))

    response = await client.post(
        f"/entities/{target.id}/merge",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_entity_id": str(source.id)},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(target.id)


async def test_merge_endpoint_rejects_missing_token(client):
    target = await _create_entity(_unique("Acme Corporation"))
    response = await client.post(f"/entities/{target.id}/merge", json={"source_entity_id": str(uuid4())})
    assert response.status_code == 401
