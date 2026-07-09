from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import UserFact


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _login(client, username: str) -> tuple[str, str]:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"], username


async def _user_id_for(username: str):
    from sqlalchemy import select

    from api.models import User

    async with async_session() as db:
        return (await db.execute(select(User).where(User.username == username))).scalar_one().id


async def _create_fact(user_id, fact_type: str = "address", status: str = "pending_review") -> UserFact:
    async with async_session() as db:
        fact = UserFact(
            user_id=user_id, fact_type=fact_type, value={"text": "somewhere"},
            valid_from=date(2026, 1, 1), confidence=0.7, status=status,
        )
        db.add(fact)
        await db.commit()
        await db.refresh(fact)
        return fact


async def test_list_facts_scoped_to_current_user(client):
    token, username = await _login(client, _unique("factlistuser"))
    user_id = await _user_id_for(username)
    await _create_fact(user_id)

    _, other_username = await _login(client, _unique("factlistotheruser"))
    other_user_id = await _user_id_for(other_username)
    await _create_fact(other_user_id)

    response = await client.get("/facts", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert all(row["user_id"] == str(user_id) for row in response.json())


async def test_list_facts_as_of_filters_by_validity_period(client):
    token, username = await _login(client, _unique("factasofuser"))
    user_id = await _user_id_for(username)
    async with async_session() as db:
        db.add(UserFact(
            user_id=user_id, fact_type="address", value={"text": "old"},
            valid_from=date(2020, 1, 1), valid_to=date(2021, 1, 1), confidence=0.5,
        ))
        db.add(UserFact(
            user_id=user_id, fact_type="address", value={"text": "current"},
            valid_from=date(2026, 1, 1), valid_to=None, confidence=0.9,
        ))
        await db.commit()

    response = await client.get("/facts?as_of=2026-06-01", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    values = [row["value"]["text"] for row in response.json()]
    assert "current" in values
    assert "old" not in values


async def test_approve_fact_transitions_pending_to_confirmed(client):
    token, username = await _login(client, _unique("factapproveuser"))
    user_id = await _user_id_for(username)
    fact = await _create_fact(user_id)

    response = await client.post(f"/facts/{fact.id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


async def test_reject_fact_transitions_pending_to_rejected(client):
    token, username = await _login(client, _unique("factrejectuser"))
    user_id = await _user_id_for(username)
    fact = await _create_fact(user_id)

    response = await client.post(f"/facts/{fact.id}/reject", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


async def test_approve_already_confirmed_fact_returns_409(client):
    token, username = await _login(client, _unique("factconflictuser"))
    user_id = await _user_id_for(username)
    fact = await _create_fact(user_id, status="confirmed")

    response = await client.post(f"/facts/{fact.id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 409


async def test_approve_unknown_fact_returns_404(client):
    token, _ = await _login(client, _unique("fact404user"))
    response = await client.post(f"/facts/{uuid4()}/approve", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


async def test_list_facts_rejects_missing_token(client):
    response = await client.get("/facts")
    assert response.status_code == 401
