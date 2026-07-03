from unittest.mock import patch
from uuid import uuid4

from api.ldap_auth import LdapIdentity


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_create_and_get_case(client):
    token = await _login(client, "caserouteruser1")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/cases", headers=headers, json={"name": "Smith v. Jones", "description": "A matter"}
    )
    assert create_response.status_code == 201
    case_id = create_response.json()["id"]
    assert create_response.json()["status"] == "open"

    get_response = await client.get(f"/cases/{case_id}", headers=headers)
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["name"] == "Smith v. Jones"
    assert body["documents"] == []
    assert body["tasks"] == []
    assert body["decisions"] == []


async def test_list_cases_only_shows_the_callers_own(client):
    token_a = await _login(client, "caserouteruser2")
    token_b = await _login(client, "caserouteruser3")

    await client.post("/cases", headers={"Authorization": f"Bearer {token_a}"}, json={"name": "A's case"})
    await client.post("/cases", headers={"Authorization": f"Bearer {token_b}"}, json={"name": "B's case"})

    response = await client.get("/cases", headers={"Authorization": f"Bearer {token_a}"})
    names = {c["name"] for c in response.json()}
    assert "A's case" in names
    assert "B's case" not in names


async def test_get_case_rejects_non_owner(client):
    owner_token = await _login(client, "caserouteruser4")
    intruder_token = await _login(client, "caserouteruser5")

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {owner_token}"}, json={"name": "Owner's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {intruder_token}"})
    assert response.status_code == 403


async def test_get_case_returns_404_for_unknown_id(client):
    token = await _login(client, "caserouteruser6")
    response = await client.get(f"/cases/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


async def test_patch_case_updates_status(client):
    token = await _login(client, "caserouteruser7")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    patch_response = await client.patch(f"/cases/{case_id}", headers=headers, json={"status": "closed"})
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "closed"


async def test_patch_case_rejects_invalid_status(client):
    token = await _login(client, "caserouteruser8")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    response = await client.patch(f"/cases/{case_id}", headers=headers, json={"status": "bogus"})
    assert response.status_code == 400


async def test_patch_case_rejects_non_owner(client):
    owner_token = await _login(client, "caserouteruser9")
    intruder_token = await _login(client, "caserouteruser10")

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {owner_token}"}, json={"name": "Owner's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.patch(
        f"/cases/{case_id}", headers={"Authorization": f"Bearer {intruder_token}"}, json={"name": "Hijacked"}
    )
    assert response.status_code == 403


async def test_delete_case(client):
    token = await _login(client, "caserouteruser11")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    delete_response = await client.delete(f"/cases/{case_id}", headers=headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/cases/{case_id}", headers=headers)
    assert get_response.status_code == 404


async def test_delete_case_rejects_non_owner(client):
    owner_token = await _login(client, "caserouteruser12")
    intruder_token = await _login(client, "caserouteruser13")

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {owner_token}"}, json={"name": "Owner's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.delete(f"/cases/{case_id}", headers={"Authorization": f"Bearer {intruder_token}"})
    assert response.status_code == 403


async def test_create_case_rejects_missing_token(client):
    response = await client.post("/cases", json={"name": "x"})
    assert response.status_code == 401


async def test_create_case_rejects_empty_name(client):
    token = await _login(client, "caserouteruser21")
    response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {token}"}, json={"name": ""}
    )
    assert response.status_code == 422
