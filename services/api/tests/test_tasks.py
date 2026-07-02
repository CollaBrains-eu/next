from unittest.mock import patch

from api.ldap_auth import LdapIdentity

FAKE_EMBEDDING = [0.1] * 768


async def _login(client) -> str:
    identity = LdapIdentity(
        username="planneruser", display_name="Planner User", email="planneruser@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "planneruser", "password": "whatever"})
    return response.json()["access_token"]


async def _upload_ready_document(client, headers, text: str) -> str:
    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value=text),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        # disable the auto-extraction workflow trigger for uploads in these tests --
        # extraction itself is exercised explicitly via the /extract-tasks endpoint
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("notes.txt", text.encode(), "text/plain")}
        )
    return upload.json()["id"]


async def test_extract_tasks_persists_parsed_items(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Alice must submit the report by 2026-08-01.")

    fake_llm_output = (
        '[{"title": "Submit the report", "description": "Alice needs to submit it.", '
        '"due_date": "2026-08-01", "assignee": "Alice"}]'
    )
    with patch("api.planner_agent.chat_completion", return_value=fake_llm_output):
        response = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)

    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Submit the report"
    assert tasks[0]["due_date"] == "2026-08-01"
    assert tasks[0]["assignee"] == "Alice"
    assert tasks[0]["source"] == "planner_agent"


async def test_extract_tasks_handles_unparseable_llm_output_gracefully(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some document text with no clear tasks.")

    with patch("api.planner_agent.chat_completion", return_value="not valid json at all"):
        response = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_list_tasks_filters_by_status(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Bob should call the client.")

    fake_llm_output = '[{"title": "Call the client", "description": null, "due_date": null, "assignee": "Bob"}]'
    with patch("api.planner_agent.chat_completion", return_value=fake_llm_output):
        extracted = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)
    task_id = extracted.json()[0]["id"]

    open_tasks = await client.get("/tasks", params={"status": "open", "document_id": document_id}, headers=headers)
    assert len(open_tasks.json()) == 1

    await client.patch(f"/tasks/{task_id}", headers=headers, json={"status": "done"})

    open_tasks_after = await client.get(
        "/tasks", params={"status": "open", "document_id": document_id}, headers=headers
    )
    assert len(open_tasks_after.json()) == 0

    done_tasks = await client.get("/tasks", params={"status": "done", "document_id": document_id}, headers=headers)
    assert len(done_tasks.json()) == 1


async def test_update_task_rejects_invalid_status(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    with patch("api.planner_agent.chat_completion", return_value='[{"title": "Do a thing"}]'):
        extracted = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)
    task_id = extracted.json()[0]["id"]

    response = await client.patch(f"/tasks/{task_id}", headers=headers, json={"status": "not-a-real-status"})
    assert response.status_code == 400


async def test_extract_tasks_rejects_missing_token(client):
    response = await client.post("/documents/00000000-0000-0000-0000-000000000000/extract-tasks")
    assert response.status_code == 401


async def test_list_tasks_rejects_missing_token(client):
    response = await client.get("/tasks")
    assert response.status_code == 401
