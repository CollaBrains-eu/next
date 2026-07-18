from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from jose import jwt
from webauthn.helpers import base64url_to_bytes

from api.config import settings
from api.ldap_auth import LdapIdentity


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


def _unique_credential_id() -> bytes:
    return uuid4().bytes


def _fake_verified_registration(credential_id: bytes | None = None, sign_count: int = 0):
    return SimpleNamespace(
        credential_id=credential_id or _unique_credential_id(), credential_public_key=b"fake-public-key", sign_count=sign_count
    )


def _fake_verified_authentication(credential_id: bytes = b"cred-id-bytes", new_sign_count: int = 1):
    return SimpleNamespace(credential_id=credential_id, new_sign_count=new_sign_count)


async def test_register_begin_requires_auth(client):
    response = await client.post("/auth/webauthn/register/begin")
    assert response.status_code == 401


async def test_register_begin_returns_challenge_options(client):
    token = await _login(client, _unique("passkeyreguser"))
    response = await client.post("/auth/webauthn/register/begin", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert "challenge" in body
    assert body["rp"]["id"] == settings.webauthn_rp_id


async def test_register_complete_without_begin_returns_400(client):
    token = await _login(client, _unique("passkeynobegin"))
    response = await client.post(
        "/auth/webauthn/register/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"credential": {"id": "x", "rawId": "x", "response": {}}},
    )
    assert response.status_code == 400


async def test_register_complete_creates_credential(client):
    username = _unique("passkeyhappyuser")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}

    begin = await client.post("/auth/webauthn/register/begin", headers=headers)
    assert begin.status_code == 200

    with patch("api.webauthn_router.verify_registration_response", return_value=_fake_verified_registration()):
        complete = await client.post(
            "/auth/webauthn/register/complete",
            headers=headers,
            json={"credential": {"id": "x", "rawId": "x", "response": {}}, "label": "My Laptop"},
        )
    assert complete.status_code == 200
    body = complete.json()
    assert body["label"] == "My Laptop"

    listing = await client.get("/auth/webauthn/credentials", headers=headers)
    assert listing.status_code == 200
    labels = [row["label"] for row in listing.json()]
    assert "My Laptop" in labels


async def test_register_complete_passes_the_exact_challenge_bytes_to_verification(client):
    """Regression test for a bug where the Redis client (missing
    decode_responses=True) returned the cached challenge as bytes, and
    base64url_to_bytes() silently mis-decoded that bytes value (via str()
    formatting) instead of raising -- corrupting expected_challenge on every
    single registration. The other register/complete tests all mock
    verify_registration_response's return value without inspecting what it
    was called with, so they can't catch this class of bug."""
    username = _unique("passkeychallengetype")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}

    begin = await client.post("/auth/webauthn/register/begin", headers=headers)
    expected_challenge_bytes = base64url_to_bytes(begin.json()["challenge"])

    captured_kwargs = {}

    def fake_verify(**kwargs):
        captured_kwargs.update(kwargs)
        return _fake_verified_registration()

    with patch("api.webauthn_router.verify_registration_response", side_effect=fake_verify):
        complete = await client.post(
            "/auth/webauthn/register/complete",
            headers=headers,
            json={"credential": {"id": "x", "rawId": "x", "response": {}}},
        )
    assert complete.status_code == 200
    assert captured_kwargs["expected_challenge"] == expected_challenge_bytes


async def test_credentials_list_is_scoped_to_current_user(client):
    username_a = _unique("passkeyowner")
    token_a = await _login(client, username_a)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    await client.post("/auth/webauthn/register/begin", headers=headers_a)
    with patch("api.webauthn_router.verify_registration_response", return_value=_fake_verified_registration()):
        await client.post(
            "/auth/webauthn/register/complete", headers=headers_a, json={"credential": {"id": "x"}, "label": "A"}
        )

    username_b = _unique("passkeyother")
    token_b = await _login(client, username_b)
    headers_b = {"Authorization": f"Bearer {token_b}"}
    listing_b = await client.get("/auth/webauthn/credentials", headers=headers_b)
    assert listing_b.json() == []


async def test_delete_credential_requires_ownership(client):
    username_a = _unique("passkeydeleteowner")
    token_a = await _login(client, username_a)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    await client.post("/auth/webauthn/register/begin", headers=headers_a)
    with patch("api.webauthn_router.verify_registration_response", return_value=_fake_verified_registration()):
        created = await client.post(
            "/auth/webauthn/register/complete", headers=headers_a, json={"credential": {"id": "x"}}
        )
    credential_id = created.json()["id"]

    username_b = _unique("passkeydeleteother")
    token_b = await _login(client, username_b)
    headers_b = {"Authorization": f"Bearer {token_b}"}
    forbidden = await client.delete(f"/auth/webauthn/credentials/{credential_id}", headers=headers_b)
    assert forbidden.status_code == 404

    allowed = await client.delete(f"/auth/webauthn/credentials/{credential_id}", headers=headers_a)
    assert allowed.status_code == 204

    listing = await client.get("/auth/webauthn/credentials", headers=headers_a)
    assert listing.json() == []


async def test_login_begin_returns_session_key_and_challenge(client):
    response = await client.post("/auth/webauthn/login/begin")
    assert response.status_code == 200
    body = response.json()
    assert "session_key" in body
    assert "challenge" in body


async def test_login_complete_with_unrecognized_credential_returns_401(client):
    begin = await client.post("/auth/webauthn/login/begin")
    session_key = begin.json()["session_key"]

    response = await client.post(
        "/auth/webauthn/login/complete",
        json={"session_key": session_key, "credential": {"id": "bm9wZQ", "rawId": "bm9wZQ"}},
    )
    assert response.status_code == 401


async def test_login_complete_with_expired_session_returns_400(client):
    response = await client.post(
        "/auth/webauthn/login/complete",
        json={"session_key": "never-existed", "credential": {"id": "eA", "rawId": "eA"}},
    )
    assert response.status_code == 400


async def test_login_complete_issues_a_valid_token_and_updates_sign_count(client):
    from webauthn.helpers import bytes_to_base64url

    username = _unique("passkeyloginuser")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    raw_credential_id = _unique_credential_id()

    await client.post("/auth/webauthn/register/begin", headers=headers)
    with patch(
        "api.webauthn_router.verify_registration_response",
        return_value=_fake_verified_registration(credential_id=raw_credential_id),
    ):
        await client.post("/auth/webauthn/register/complete", headers=headers, json={"credential": {"id": "x"}})

    begin = await client.post("/auth/webauthn/login/begin")
    session_key = begin.json()["session_key"]
    encoded_id = bytes_to_base64url(raw_credential_id)

    with patch(
        "api.webauthn_router.verify_authentication_response",
        return_value=_fake_verified_authentication(credential_id=raw_credential_id, new_sign_count=7),
    ):
        complete = await client.post(
            "/auth/webauthn/login/complete",
            json={"session_key": session_key, "credential": {"id": encoded_id, "rawId": encoded_id}},
        )
    assert complete.status_code == 200
    login_token = complete.json()["access_token"]
    payload = jwt.decode(login_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == username

    listing = await client.get("/auth/webauthn/credentials", headers=headers)
    assert listing.json()[0]["last_used_at"] is not None


async def test_login_complete_passes_the_exact_challenge_bytes_to_verification(client):
    """Same regression as test_register_complete_passes_the_exact_challenge_bytes_to_verification,
    but for the login ceremony's separate Redis key/getdel call."""
    from webauthn.helpers import bytes_to_base64url

    username = _unique("passkeyloginchallengetype")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    raw_credential_id = _unique_credential_id()

    await client.post("/auth/webauthn/register/begin", headers=headers)
    with patch(
        "api.webauthn_router.verify_registration_response",
        return_value=_fake_verified_registration(credential_id=raw_credential_id),
    ):
        await client.post("/auth/webauthn/register/complete", headers=headers, json={"credential": {"id": "x"}})

    begin = await client.post("/auth/webauthn/login/begin")
    session_key = begin.json()["session_key"]
    expected_challenge_bytes = base64url_to_bytes(begin.json()["challenge"])
    encoded_id = bytes_to_base64url(raw_credential_id)

    captured_kwargs = {}

    def fake_verify(**kwargs):
        captured_kwargs.update(kwargs)
        return _fake_verified_authentication(credential_id=raw_credential_id)

    with patch("api.webauthn_router.verify_authentication_response", side_effect=fake_verify):
        complete = await client.post(
            "/auth/webauthn/login/complete",
            json={"session_key": session_key, "credential": {"id": encoded_id, "rawId": encoded_id}},
        )
    assert complete.status_code == 200
    assert captured_kwargs["expected_challenge"] == expected_challenge_bytes


async def test_login_complete_challenge_is_single_use(client):
    begin = await client.post("/auth/webauthn/login/begin")
    session_key = begin.json()["session_key"]
    payload = {"session_key": session_key, "credential": {"id": "bm9wZQ", "rawId": "bm9wZQ"}}

    first = await client.post("/auth/webauthn/login/complete", json=payload)
    assert first.status_code == 401  # unrecognized credential, but challenge was consumed

    second = await client.post("/auth/webauthn/login/complete", json=payload)
    assert second.status_code == 400  # challenge already used
