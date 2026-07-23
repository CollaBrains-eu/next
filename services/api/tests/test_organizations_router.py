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


async def test_is_org_admin_reflects_ownership_not_just_platform_role(client):
    """ADR 0074: is_org_admin must be true for a platform admin OR the
    org's owner_user_id, and false for a plain member with neither."""
    from api.db import async_session
    from api.models import Organization, User

    plain_token = await _login(client, _unique("orgisadminplain"))
    plain_response = await client.get("/organizations/me", headers={"Authorization": f"Bearer {plain_token}"})
    assert plain_response.json()["is_org_admin"] is False

    admin_token = await _login(client, _unique("orgisadminplatform"), is_admin=True)
    admin_response = await client.get("/organizations/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_response.json()["is_org_admin"] is True

    owner_username = _unique("orgisadminowner")
    owner_token = await _login(client, owner_username)
    from sqlalchemy import select

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == owner_username))).scalar_one()
        organization = await db.get(Organization, DEFAULT_ORGANIZATION_ID)
        organization.owner_user_id = user.id
        await db.commit()

    try:
        owner_response = await client.get("/organizations/me", headers={"Authorization": f"Bearer {owner_token}"})
        assert owner_response.json()["is_org_admin"] is True
    finally:
        async with async_session() as db:
            organization = await db.get(Organization, DEFAULT_ORGANIZATION_ID)
            organization.owner_user_id = None
            await db.commit()


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


async def test_org_owner_without_platform_admin_role_can_manage_their_own_org(client):
    """A self-service signup (ADR 0074) is `Organization.owner_user_id`,
    not platform `role == "admin"` -- this confirms that's actually
    sufficient to manage the org, not just a inert marker."""
    from api.models import Organization

    username = _unique("orgowner")
    token = await _login(client, username, is_admin=False)
    headers = {"Authorization": f"Bearer {token}"}

    org = await client.get("/organizations/me", headers=headers)
    org_id = org.json()["id"]

    async with async_session() as db:
        from sqlalchemy import select

        from api.models import User

        user = (await db.execute(select(User).where(User.username == username))).scalar_one()
        organization = await db.get(Organization, org_id)
        organization.owner_user_id = user.id
        await db.commit()

    try:
        rename_response = await client.put(
            "/organizations/me", headers=headers, json={"name": "Owner-Managed Org"}
        )
        assert rename_response.status_code == 200
        assert rename_response.json()["name"] == "Owner-Managed Org"

        policies_response = await client.put(
            "/organizations/me/policies", headers=headers, json={"policies": {"approval_required_goals": []}}
        )
        assert policies_response.status_code == 200
    finally:
        async with async_session() as db:
            organization = await db.get(Organization, org_id)
            organization.owner_user_id = None
            await db.commit()
        async with async_session() as db:
            await rename_organization(db, organization_id=org_id, name=org.json()["name"])
            await set_organization_policies(db, organization_id=org_id, policies={})
