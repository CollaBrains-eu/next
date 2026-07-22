import uuid
from unittest.mock import patch

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Case, CaseMember, Document, Entity, Task, User

# This backend test suite shares one live Postgres with no per-test
# transaction rollback (documented, pre-existing project constraint) -- a
# fixed username re-run against the same DB reuses the same auto-created
# User row (get-or-create on login) and accumulates duplicate fixture data
# across runs. A per-module-load random suffix keeps every run's usernames
# (and therefore every row they own) fresh, regardless of how many times
# this file is re-run against the same database.
_RUN_ID = uuid.uuid4().hex[:8]


def _u(n: int) -> str:
    return f"dashboarduser{n}_{_RUN_ID}"


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_id_for(username: str):
    async with async_session() as db:
        return (await db.execute(select(User).where(User.username == username))).scalar_one().id


async def _create_document(owner_id, title: str = "t") -> Document:
    async with async_session() as db:
        document = Document(owner_id=owner_id, title=title, filename="t.pdf", mime_type="application/pdf", status="ready")
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def _create_task(*, created_by=None, document_id=None, title: str = "Do the thing") -> Task:
    async with async_session() as db:
        task = Task(title=title, source="manual", created_by=created_by, document_id=document_id)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task


async def _create_case(user_id, name: str = "A case") -> Case:
    async with async_session() as db:
        case = Case(user_id=user_id, name=name)
        db.add(case)
        await db.commit()
        await db.refresh(case)
        return case


async def _create_entity(owner_id, name: str = "Acme Corp") -> Entity:
    async with async_session() as db:
        entity = Entity(owner_id=owner_id, name=name, entity_type="organization")
        db.add(entity)
        await db.commit()
        await db.refresh(entity)
        return entity


async def test_activity_excludes_another_users_document(client):
    await _login(client, _u(1))
    user_a_id = await _user_id_for(_u(1))
    token_b = await _login(client, _u(2))

    await _create_document(user_a_id, title="User A's document")

    response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 200
    assert "User A's document" not in [item["title"] for item in response.json()]


async def test_activity_includes_the_current_users_own_document(client):
    token = await _login(client, _u(3))
    user_id = await _user_id_for(_u(3))
    await _create_document(user_id, title="My document")

    response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    matching = [item for item in response.json() if item["title"] == "My document"]
    assert len(matching) == 1
    assert matching[0]["type"] == "document"
    assert matching[0]["link"] == f"/documents/{matching[0]['id']}"


async def test_activity_includes_a_case_only_after_membership_is_accepted(client):
    await _login(client, _u(4))
    owner_id = await _user_id_for(_u(4))
    member_token = await _login(client, _u(5))
    member_id = await _user_id_for(_u(5))

    case = await _create_case(owner_id, name="Shared case")
    async with async_session() as db:
        db.add(CaseMember(case_id=case.id, user_id=member_id, status="pending"))
        await db.commit()

    pending_response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {member_token}"})
    assert "Shared case" not in [item["title"] for item in pending_response.json()]

    async with async_session() as db:
        row = (
            await db.execute(select(CaseMember).where(CaseMember.case_id == case.id, CaseMember.user_id == member_id))
        ).scalar_one()
        row.status = "accepted"
        await db.commit()

    accepted_response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {member_token}"})
    assert "Shared case" in [item["title"] for item in accepted_response.json()]


async def test_activity_includes_an_unassigned_task_via_its_documents_owner(client):
    token = await _login(client, _u(6))
    user_id = await _user_id_for(_u(6))
    document = await _create_document(user_id, title="Doc with a task")
    await _create_task(created_by=None, document_id=document.id, title="Extracted task")

    response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {token}"})
    matching = [item for item in response.json() if item["type"] == "task" and item["title"] == "Extracted task"]
    assert len(matching) == 1
    assert matching[0]["link"] == f"/documents/{document.id}"


async def test_activity_merges_and_sorts_all_types_by_recency(client):
    token = await _login(client, _u(7))
    user_id = await _user_id_for(_u(7))
    await _create_document(user_id, title="Oldest")
    await _create_task(created_by=user_id, title="Middle")
    await _create_case(user_id, name="Newest")

    response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {token}"})
    ordered_titles = [item["title"] for item in response.json() if item["title"] in {"Oldest", "Middle", "Newest"}]
    assert ordered_titles == ["Newest", "Middle", "Oldest"]


async def test_activity_includes_the_current_users_entity_including_pending_review(client):
    token = await _login(client, _u(8))
    user_id = await _user_id_for(_u(8))
    await _create_entity(user_id, name="Pending Co")

    response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {token}"})
    matching = [item for item in response.json() if item["type"] == "entity" and item["title"] == "Pending Co"]
    assert len(matching) == 1
    assert matching[0]["link"] == f"/entities/{matching[0]['id']}"
