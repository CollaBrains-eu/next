from unittest.mock import patch

from api.ldap_auth import LdapIdentity


def _fake_identity(is_admin: bool) -> LdapIdentity:
    return LdapIdentity(
        username="testadmin" if is_admin else "testuser",
        display_name="Test Admin" if is_admin else "Test User",
        email="testuser@collabrains.eu",
        is_admin=is_admin,
    )


async def test_login_provisions_member_on_first_login(client):
    with patch("api.auth.ldap_authenticate", return_value=_fake_identity(is_admin=False)):
        login = await client.post("/auth/token", data={"username": "testuser", "password": "whatever"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "testuser"
    assert body["role"] == "member"


async def test_login_provisions_admin_from_ldap_group(client):
    with patch("api.auth.ldap_authenticate", return_value=_fake_identity(is_admin=True)):
        login = await client.post("/auth/token", data={"username": "testadmin", "password": "whatever"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "admin"


async def test_login_rejects_bad_ldap_credentials(client):
    with patch("api.auth.ldap_authenticate", return_value=None):
        response = await client.post("/auth/token", data={"username": "testuser", "password": "wrong"})
    assert response.status_code == 401


async def test_me_rejects_missing_token(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401
