from unittest.mock import patch

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import DEFAULT_ORGANIZATION_ID
from api.organizations import set_organization_policies


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
