from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import ShareLink, User
from api.sharing import create_or_rotate_share_link, get_valid_share_link


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_id_for(username: str):
    async with async_session() as db:
        return (await db.execute(select(User).where(User.username == username))).scalar_one().id


async def test_create_or_rotate_share_link_creates_then_rotates(client):
    await _login(client, "sharesvcuser1")
    user_id = await _user_id_for("sharesvcuser1")
    entity_id = uuid4()

    async with async_session() as db:
        first = await create_or_rotate_share_link(
            db, entity_type="document", entity_id=entity_id, created_by_user_id=user_id,
        )
        # Capture as plain values before rotating -- `first` and the object
        # returned by the second call are the same SQLAlchemy identity-mapped
        # instance (same session, same PK), so comparing attributes on the
        # live objects after the second call would always show them equal.
        first_id, first_token = first.id, first.token

        second = await create_or_rotate_share_link(
            db, entity_type="document", entity_id=entity_id, created_by_user_id=user_id,
        )

    assert first_id == second.id
    assert first_token != second.token


async def test_get_valid_share_link_returns_none_for_expired_token(client):
    await _login(client, "sharesvcuser2")
    user_id = await _user_id_for("sharesvcuser2")
    token = f"expired-token-{uuid4().hex}"

    async with async_session() as db:
        link = ShareLink(
            entity_type="task", entity_id=uuid4(), token=token,
            created_by_user_id=user_id, expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(link)
        await db.commit()

        found = await get_valid_share_link(db, token=token)

    assert found is None


async def test_create_share_link_endpoint_requires_auth(client):
    response = await client.post("/share", json={"entity_type": "task", "entity_id": str(uuid4())})
    assert response.status_code == 401


async def test_create_share_link_rejects_non_owner(client):
    owner_token = await _login(client, "sharerouteruser1")
    intruder_token = await _login(client, "sharerouteruser2")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

    task_id = (await client.post("/tasks", headers=owner_headers, json={"title": "Owner task"})).json()["id"]

    response = await client.post(
        "/share", headers=intruder_headers, json={"entity_type": "task", "entity_id": task_id}
    )
    assert response.status_code == 403


async def test_share_and_resolve_task_as_logged_in_user(client):
    owner_token = await _login(client, "sharerouteruser3")
    other_token = await _login(client, "sharerouteruser4")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    task_id = (await client.post("/tasks", headers=owner_headers, json={"title": "Shared task"})).json()["id"]

    share_response = await client.post(
        "/share", headers=owner_headers, json={"entity_type": "task", "entity_id": task_id}
    )
    assert share_response.status_code == 201
    token = share_response.json()["token"]

    # A different, unrelated but logged-in user can resolve it -- that's the
    # whole point of a share link (bypasses task ownership, still requires login).
    resolve_response = await client.get(f"/share/{token}", headers=other_headers)
    assert resolve_response.status_code == 200
    body = resolve_response.json()
    assert body["entity_type"] == "task"
    assert body["data"]["title"] == "Shared task"


async def test_resolve_share_link_requires_auth(client):
    response = await client.get("/share/some-token")
    assert response.status_code == 401


async def test_resolve_unknown_token_returns_404(client):
    token = await _login(client, "sharerouteruser5")
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/share/not-a-real-token", headers=headers)
    assert response.status_code == 404


async def test_share_and_resolve_case(client):
    owner_token = await _login(client, "sharerouteruser6")
    other_token = await _login(client, "sharerouteruser7")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    case_id = (await client.post("/cases", headers=owner_headers, json={"name": "Shared case"})).json()["id"]

    share_response = await client.post(
        "/share", headers=owner_headers, json={"entity_type": "case", "entity_id": case_id}
    )
    token = share_response.json()["token"]

    resolve_response = await client.get(f"/share/{token}", headers=other_headers)
    assert resolve_response.status_code == 200
    assert resolve_response.json()["data"]["name"] == "Shared case"
