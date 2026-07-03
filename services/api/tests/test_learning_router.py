from unittest.mock import patch


async def _login(client, username: str, *, is_admin: bool = False) -> str:
    from api.ldap_auth import LdapIdentity

    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_get_dataset_requires_admin_role(client):
    token = await _login(client, "learningrouteruser1", is_admin=False)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/learning/dataset", headers=headers)
    assert response.status_code == 403


async def test_admin_can_fetch_the_dataset(client):
    token = await _login(client, "learningrouteruser2", is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/learning/dataset", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert "generated_at" in body
    assert "plan_approval_examples" in body
    assert "reflection_examples" in body


async def test_get_dataset_rejects_missing_token(client):
    response = await client.get("/learning/dataset")
    assert response.status_code == 401
