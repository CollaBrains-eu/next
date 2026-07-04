from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from api.db import async_session
from api.knowledge_graph import create_decision_from_plan
from api.ldap_auth import LdapIdentity
from api.models import Document, User
from api.planning_engine import create_plan


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _login(client, base_username: str) -> tuple[str, str]:
    username = _unique(base_username)
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"], username


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


async def _user_id_for(username: str):
    async with async_session() as db:
        return (await db.execute(select(User).where(User.username == username))).scalar_one().id


async def test_get_decision_returns_supporting_documents(client):
    token, username = await _login(client, "decisionuser")
    user_id = await _user_id_for(username)
    document = await _create_document(user_id)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=user_id, goal_type="draft_legal_document",
            goal_params={"instruction": "Draft a notice.", "document_ids": [str(document.id)]},
        )
        decision = await create_decision_from_plan(db, plan=plan, user_id=user_id)

    response = await client.get(f"/decisions/{decision.id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == decision.summary
    assert [doc["id"] for doc in body["supporting_documents"]] == [str(document.id)]


async def test_list_decisions_scoped_to_user(client):
    owner_token, owner_username = await _login(client, "decisionlistuser")
    owner_id = await _user_id_for(owner_username)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=owner_id, goal_type="draft_legal_document", goal_params={"instruction": "Draft a notice."},
        )
        decision = await create_decision_from_plan(db, plan=plan, user_id=owner_id)

    other_token, other_username = await _login(client, "decisionlistother")
    other_id = await _user_id_for(other_username)
    async with async_session() as db:
        other_plan = await create_plan(
            db, user_id=other_id, goal_type="draft_legal_document",
            goal_params={"instruction": "Draft another notice."},
        )
        await create_decision_from_plan(db, plan=other_plan, user_id=other_id)

    response = await client.get("/decisions", headers={"Authorization": f"Bearer {owner_token}"})
    assert response.status_code == 200
    ids = [d["id"] for d in response.json()]
    assert ids == [str(decision.id)]


async def test_list_decisions_rejects_missing_token(client):
    response = await client.get("/decisions")
    assert response.status_code == 401


async def test_get_decision_rejects_non_owner(client):
    owner_token, owner_username = await _login(client, "decisionowner")
    owner_id = await _user_id_for(owner_username)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=owner_id, goal_type="draft_legal_document", goal_params={"instruction": "Draft a notice."},
        )
        decision = await create_decision_from_plan(db, plan=plan, user_id=owner_id)

    intruder_token, _ = await _login(client, "decisionintruder")

    response = await client.get(
        f"/decisions/{decision.id}", headers={"Authorization": f"Bearer {intruder_token}"}
    )
    assert response.status_code == 403


async def test_get_decision_returns_404_for_unknown_id(client):
    token, _ = await _login(client, "decisionuser")
    response = await client.get(f"/decisions/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


async def test_get_decision_rejects_missing_token(client):
    response = await client.get(f"/decisions/{uuid4()}")
    assert response.status_code == 401
