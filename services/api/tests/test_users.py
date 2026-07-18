from unittest.mock import patch
from uuid import uuid4

from api.ldap_auth import LdapIdentity


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


def _unique_phone() -> str:
    return f"+1555{uuid4().int % 10_000_000:07d}"


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_lookup_finds_a_user_by_exact_phone_number(client):
    target_username = _unique("phonelookuptarget")
    target_token = await _login(client, target_username)
    phone = _unique_phone()
    link_response = await client.put(
        "/auth/me/phone", headers={"Authorization": f"Bearer {target_token}"}, json={"phone_number": phone}
    )
    assert link_response.status_code == 200

    caller_token = await _login(client, _unique("phonelookupcaller"))
    response = await client.get(
        "/users/lookup", params={"phone": phone}, headers={"Authorization": f"Bearer {caller_token}"}
    )

    assert response.status_code == 200
    assert response.json()["username"] == target_username


async def test_lookup_returns_404_for_unknown_phone_number(client):
    caller_token = await _login(client, _unique("phonelookupcaller2"))
    response = await client.get(
        "/users/lookup", params={"phone": _unique_phone()}, headers={"Authorization": f"Bearer {caller_token}"}
    )
    assert response.status_code == 404


async def test_lookup_rejects_non_e164_phone_number(client):
    caller_token = await _login(client, _unique("phonelookupcaller3"))
    response = await client.get(
        "/users/lookup", params={"phone": "0611234567"}, headers={"Authorization": f"Bearer {caller_token}"}
    )
    assert response.status_code == 400


async def test_lookup_requires_auth(client):
    response = await client.get("/users/lookup", params={"phone": _unique_phone()})
    assert response.status_code == 401


async def test_lookup_does_not_partial_match(client):
    target_username = _unique("phonelookuppartial")
    target_token = await _login(client, target_username)
    phone = _unique_phone()
    await client.put(
        "/auth/me/phone", headers={"Authorization": f"Bearer {target_token}"}, json={"phone_number": phone}
    )

    caller_token = await _login(client, _unique("phonelookupcaller4"))
    response = await client.get(
        "/users/lookup", params={"phone": phone[:-1]}, headers={"Authorization": f"Bearer {caller_token}"}
    )
    assert response.status_code == 404
