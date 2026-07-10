from unittest.mock import patch

from api.ldap_auth import LdapIdentity


async def _login(client) -> str:
    identity = LdapIdentity(
        username="catuser", display_name="Cat User", email="catuser@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "catuser", "password": "whatever"})
    return response.json()["access_token"]


async def test_list_categories_returns_the_document_taxonomy(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/categories", headers=headers, params={"category_type": "document"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) > 20  # the full taxonomy, not a trimmed placeholder
    slugs = {c["slug"] for c in body}
    assert "payslip" in slugs
    assert "medical_care" in slugs
    assert all("name" not in c for c in body)


async def test_list_categories_rejects_missing_token(client):
    response = await client.get("/categories", params={"category_type": "document"})
    assert response.status_code == 401
