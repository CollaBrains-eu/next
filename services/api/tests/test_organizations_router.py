from unittest.mock import patch
from uuid import uuid4

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import DEFAULT_ORGANIZATION_ID
from api.organizations import rename_organization, set_organization_policies


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _login(client, username: str, *, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_get_my_organization_returns_the_default_organization(client):
    token = await _login(client, "orgrouteruser1")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/organizations/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(DEFAULT_ORGANIZATION_ID)


async def test_set_policies_requires_admin_role(client):
    token = await _login(client, "orgrouteruser2", is_admin=False)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put(
        "/organizations/me/policies", headers=headers, json={"policies": {"approval_required_goals": []}}
    )
    assert response.status_code == 403


async def test_admin_can_set_and_read_back_policies(client):
    token = await _login(client, "orgrouteruser3", is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        put_response = await client.put(
            "/organizations/me/policies",
            headers=headers,
            json={"policies": {"approval_required_goals": ["summarize_case"]}},
        )
        assert put_response.status_code == 200
        assert put_response.json()["policies"] == {"approval_required_goals": ["summarize_case"]}

        get_response = await client.get("/organizations/me", headers=headers)
        assert get_response.json()["policies"] == {"approval_required_goals": ["summarize_case"]}
    finally:
        async with async_session() as db:
            await set_organization_policies(db, organization_id=DEFAULT_ORGANIZATION_ID, policies={})


async def test_get_my_organization_rejects_missing_token(client):
    response = await client.get("/organizations/me")
    assert response.status_code == 401


async def test_list_members_includes_the_caller_and_is_ordered_by_username(client):
    # Two usernames sharing a fixed prefix and differing only in the last
    # character, so their relative order is unambiguous under any collation
    # -- unlike a full-list Python sort, which disagrees with Postgres's
    # (locale-aware, case-insensitive-ish) collation on mixed-case usernames.
    username_a = _unique("zzzorgmembera")
    username_b = _unique("zzzorgmemberb")
    token_a = await _login(client, username_a)
    await _login(client, username_b)
    headers = {"Authorization": f"Bearer {token_a}"}

    response = await client.get("/organizations/me/members", headers=headers)

    assert response.status_code == 200
    body = response.json()
    usernames = [row["username"] for row in body]
    assert username_a in usernames
    assert username_b in usernames
    assert usernames.index(username_a) < usernames.index(username_b)

    caller_row = next(row for row in body if row["username"] == username_a)
    assert caller_row["display_name"] == username_a
    assert caller_row["role"] == "member"


async def test_list_members_rejects_missing_token(client):
    response = await client.get("/organizations/me/members")
    assert response.status_code == 401


async def test_rename_requires_admin_role(client):
    token = await _login(client, _unique("orgrenamemember"), is_admin=False)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put("/organizations/me", headers=headers, json={"name": "New Name"})
    assert response.status_code == 403


async def test_admin_can_rename_organization(client):
    token = await _login(client, _unique("orgrenameadmin"), is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = await client.put("/organizations/me", headers=headers, json={"name": "Renamed Org"})
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed Org"

        get_response = await client.get("/organizations/me", headers=headers)
        assert get_response.json()["name"] == "Renamed Org"
    finally:
        async with async_session() as db:
            await rename_organization(db, organization_id=DEFAULT_ORGANIZATION_ID, name="Default Organization")


async def test_rename_rejects_empty_name(client):
    token = await _login(client, _unique("orgrenameemptyadmin"), is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put("/organizations/me", headers=headers, json={"name": ""})
    assert response.status_code == 422
