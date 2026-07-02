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


async def _get_token(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_link_phone_number_succeeds_and_shows_up_on_me(client):
    token = await _get_token(client, "phoneuser1")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put("/auth/me/phone", headers=headers, json={"phone_number": "+15551230001"})
    assert response.status_code == 200
    assert response.json()["phone_number"] == "+15551230001"

    me = await client.get("/auth/me", headers=headers)
    assert me.json()["phone_number"] == "+15551230001"


async def test_link_phone_number_rejects_non_e164_format(client):
    token = await _get_token(client, "phoneuser2")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put("/auth/me/phone", headers=headers, json={"phone_number": "0491511234567"})
    assert response.status_code == 400


async def test_link_phone_number_rejects_duplicate(client):
    token1 = await _get_token(client, "phoneuser3")
    token2 = await _get_token(client, "phoneuser4")

    first = await client.put(
        "/auth/me/phone", headers={"Authorization": f"Bearer {token1}"}, json={"phone_number": "+15551230099"}
    )
    assert first.status_code == 200

    second = await client.put(
        "/auth/me/phone", headers={"Authorization": f"Bearer {token2}"}, json={"phone_number": "+15551230099"}
    )
    assert second.status_code == 409
