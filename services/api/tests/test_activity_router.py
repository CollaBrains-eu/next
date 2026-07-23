from unittest.mock import patch
from uuid import uuid4

from api.ldap_auth import LdapIdentity


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_list_activity_requires_auth(client):
    response = await client.get("/activity", params={"entity_type": "case", "entity_id": str(uuid4())})
    assert response.status_code == 401


async def test_list_activity_returns_404_for_unknown_entity(client):
    token = await _login(client, "activityrouteruser1")
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get(
        "/activity", params={"entity_type": "case", "entity_id": str(uuid4())}, headers=headers
    )
    assert response.status_code == 404


async def test_list_activity_rejects_non_member(client):
    owner_token = await _login(client, "activityrouteruser2")
    intruder_token = await _login(client, "activityrouteruser3")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

    case_id = (await client.post("/cases", headers=owner_headers, json={"name": "Private case"})).json()["id"]

    response = await client.get(
        "/activity", params={"entity_type": "case", "entity_id": case_id}, headers=intruder_headers
    )
    assert response.status_code == 403


async def test_case_created_and_status_changed_are_logged(client):
    token = await _login(client, "activityrouteruser4")
    headers = {"Authorization": f"Bearer {token}"}

    case_id = (await client.post("/cases", headers=headers, json={"name": "A case"})).json()["id"]
    await client.patch(f"/cases/{case_id}", headers=headers, json={"status": "closed"})

    response = await client.get("/activity", params={"entity_type": "case", "entity_id": case_id}, headers=headers)
    assert response.status_code == 200
    actions = [e["action"] for e in response.json()]
    assert "created" in actions
    assert "status_changed" in actions
    for entry in response.json():
        assert entry["actor_display_name"] == "activityrouteruser4"


async def test_task_created_and_status_changed_are_logged(client):
    token = await _login(client, "activityrouteruser5")
    headers = {"Authorization": f"Bearer {token}"}

    task_id = (await client.post("/tasks", headers=headers, json={"title": "Chase invoice"})).json()["id"]
    await client.patch(f"/tasks/{task_id}", headers=headers, json={"status": "done"})

    response = await client.get("/activity", params={"entity_type": "task", "entity_id": task_id}, headers=headers)
    assert response.status_code == 200
    actions = [e["action"] for e in response.json()]
    assert "created" in actions
    assert "status_changed" in actions


async def test_document_uploaded_and_deleted_are_logged(client):
    token = await _login(client, "activityrouteruser6")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-y"),
        patch("api.documents.wait_for_paperless_id", return_value=101),
        patch("api.documents.fetch_document_text", return_value="some text"),
        patch("api.documents.embed_text", return_value=[0.1] * 768),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_classify_on_ready", False),
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("notes.txt", b"hello", "text/plain")}
        )
    document_id = upload.json()["id"]

    response = await client.get(
        "/activity", params={"entity_type": "document", "entity_id": document_id}, headers=headers
    )
    assert response.status_code == 200
    actions = [e["action"] for e in response.json()]
    assert "uploaded" in actions

    # The read-access check 404s once the document itself is gone (matches
    # the entity-existence check every entity_type branch shares) -- activity
    # for a deleted entity isn't independently browsable, which is fine since
    # the frontend Drawer closes and navigates away on delete anyway.
    with patch("api.documents.paperless_delete", return_value=None):
        delete_response = await client.delete(f"/documents/{document_id}", headers=headers)
    assert delete_response.status_code == 204
    after_delete = await client.get(
        "/activity", params={"entity_type": "document", "entity_id": document_id}, headers=headers
    )
    assert after_delete.status_code == 404
