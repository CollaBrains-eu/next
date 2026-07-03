from unittest.mock import patch

from api.ldap_auth import LdapIdentity


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_get_preferences_returns_null_when_unset(client):
    token = await _login(client, "prefrouteruser1")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/preferences/me", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"preferred_language": None}


async def test_set_and_get_preferences_round_trip(client):
    token = await _login(client, "prefrouteruser2")
    headers = {"Authorization": f"Bearer {token}"}

    put_response = await client.put("/preferences/me", headers=headers, json={"preferred_language": "de"})
    assert put_response.status_code == 200
    assert put_response.json() == {"preferred_language": "de"}

    get_response = await client.get("/preferences/me", headers=headers)
    assert get_response.json() == {"preferred_language": "de"}


async def test_delete_preferences(client):
    token = await _login(client, "prefrouteruser3")
    headers = {"Authorization": f"Bearer {token}"}

    await client.put("/preferences/me", headers=headers, json={"preferred_language": "nl"})

    delete_response = await client.delete("/preferences/me", headers=headers)
    assert delete_response.status_code == 204

    get_response = await client.get("/preferences/me", headers=headers)
    assert get_response.json() == {"preferred_language": None}


async def test_delete_preferences_returns_404_when_nothing_to_delete(client):
    token = await _login(client, "prefrouteruser4")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete("/preferences/me", headers=headers)
    assert response.status_code == 404


async def test_preferences_endpoints_are_scoped_to_the_caller(client):
    token_a = await _login(client, "prefrouteruserA")
    token_b = await _login(client, "prefrouteruserB")

    await client.put(
        "/preferences/me", headers={"Authorization": f"Bearer {token_a}"}, json={"preferred_language": "de"}
    )

    response_b = await client.get("/preferences/me", headers={"Authorization": f"Bearer {token_b}"})
    assert response_b.json() == {"preferred_language": None}


async def test_get_preferences_rejects_missing_token(client):
    response = await client.get("/preferences/me")
    assert response.status_code == 401
