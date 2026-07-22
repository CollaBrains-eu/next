from uuid import uuid4

from api.activity import list_activity, log_activity
from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import User
from unittest.mock import patch


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_id_for(username: str):
    from sqlalchemy import select

    async with async_session() as db:
        return (await db.execute(select(User).where(User.username == username))).scalar_one().id


async def test_log_and_list_activity_round_trips(client):
    await _login(client, "activitysvcuser1")
    user_id = await _user_id_for("activitysvcuser1")
    entity_id = uuid4()

    async with async_session() as db:
        await log_activity(
            db, entity_type="document", entity_id=entity_id, action="uploaded",
            actor_user_id=user_id, detail={"filename": "a.pdf"},
        )
        await log_activity(
            db, entity_type="document", entity_id=entity_id, action="summarized",
            actor_user_id=user_id,
        )

        entries = await list_activity(db, entity_type="document", entity_id=entity_id)

    assert [e.action for e in entries] == ["summarized", "uploaded"]  # newest first
    assert entries[1].detail == {"filename": "a.pdf"}
    assert entries[0].detail == {}


async def test_list_activity_filters_by_entity_id(client):
    await _login(client, "activitysvcuser2")
    user_id = await _user_id_for("activitysvcuser2")
    entity_a = uuid4()
    entity_b = uuid4()

    async with async_session() as db:
        await log_activity(db, entity_type="task", entity_id=entity_a, action="created", actor_user_id=user_id)
        await log_activity(db, entity_type="task", entity_id=entity_b, action="created", actor_user_id=user_id)

        entries = await list_activity(db, entity_type="task", entity_id=entity_a)

    assert len(entries) == 1
    assert entries[0].entity_id == entity_a
