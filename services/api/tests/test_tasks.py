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


async def test_update_task_accepts_in_progress_status(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    with patch("api.planner_agent.chat_completion", return_value='[{"title": "Do a thing"}]'):
        extracted = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)
    task_id = extracted.json()[0]["id"]

    response = await client.patch(f"/tasks/{task_id}", headers=headers, json={"status": "in_progress"})
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


async def test_extracted_task_defaults_to_position_zero(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    with patch("api.planner_agent.chat_completion", return_value='[{"title": "Do a thing"}]'):
        extracted = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)

    assert extracted.json()[0]["position"] == 0


async def test_moving_task_to_new_column_appends_to_end_when_no_position_given(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    with patch(
        "api.planner_agent.chat_completion",
        return_value='[{"title": "Task A"}, {"title": "Task B"}]',
    ):
        extracted = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)
    task_a, task_b = extracted.json()

    # Move both into "in_progress" without specifying a position -- each should
    # append after the other, not collide on the same position. The column is
    # global (not scoped to this test's document), and this DB is shared
    # across test runs, so assert the relative order, not absolute values.
    resp_a = await client.patch(
        f"/tasks/{task_a['id']}", headers=headers, json={"status": "in_progress"}
    )
    resp_b = await client.patch(
        f"/tasks/{task_b['id']}", headers=headers, json={"status": "in_progress"}
    )

    assert resp_b.json()["position"] == resp_a.json()["position"] + 1


async def test_moving_task_to_explicit_position_shifts_siblings(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    with patch(
        "api.planner_agent.chat_completion",
        return_value='[{"title": "Task A"}, {"title": "Task B"}, {"title": "Task C"}]',
    ):
        extracted = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)
    task_a, task_b, task_c = extracted.json()

    # All three start at position 0 within "open" (each extracted task defaults
    # to position 0 -- extraction doesn't sequence siblings). Move C to the
    # front explicitly.
    resp_c = await client.patch(
        f"/tasks/{task_c['id']}", headers=headers, json={"status": "open", "position": 0}
    )
    assert resp_c.json()["position"] == 0

    listed = await client.get("/tasks", params={"status": "open", "document_id": document_id}, headers=headers)
    positions = {t["id"]: t["position"] for t in listed.json()}
    assert positions[task_c["id"]] == 0
    # A and B, previously both at position 0, must now occupy distinct slots
    # after C's insert -- no two tasks in the same column share a position.
    assert len({positions[task_a["id"]], positions[task_b["id"]], positions[task_c["id"]]}) == 3


async def test_reordering_within_same_column_does_not_duplicate_positions(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    with patch(
        "api.planner_agent.chat_completion",
        return_value='[{"title": "Task A"}, {"title": "Task B"}, {"title": "Task C"}]',
    ):
        extracted = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)
    task_a, task_b, task_c = extracted.json()

    # Sequence them via append-moves into "in_progress" -- a column that may
    # already hold other tasks from other tests sharing this DB.
    for t in (task_a, task_b, task_c):
        await client.patch(f"/tasks/{t['id']}", headers=headers, json={"status": "in_progress"})

    column_before = await client.get(
        "/tasks", params={"status": "in_progress", "limit": 200}, headers=headers
    )
    last_position = len(column_before.json()) - 1

    # Move the first of our three tasks to the very end of the column.
    resp = await client.patch(
        f"/tasks/{task_a['id']}", headers=headers, json={"status": "in_progress", "position": last_position}
    )
    assert resp.json()["position"] == last_position

    listed = await client.get(
        "/tasks", params={"status": "in_progress", "limit": 200}, headers=headers
    )
    our_ids = {task_a["id"], task_b["id"], task_c["id"]}
    our_positions = [t["position"] for t in listed.json() if t["id"] in our_ids]
    assert len(our_positions) == 3
    # No two of our three tasks share a position after the reorder.
    assert len(set(our_positions)) == 3


async def test_update_task_rejects_status_outside_allowed_set(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    with patch("api.planner_agent.chat_completion", return_value='[{"title": "Do a thing"}]'):
        extracted = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)
    task_id = extracted.json()[0]["id"]

    response = await client.patch(f"/tasks/{task_id}", headers=headers, json={"status": "archived"})
    assert response.status_code == 400


async def test_create_task_manually(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/tasks",
        headers=headers,
        json={"title": "Chase missing invoice", "due_date": "2026-08-01", "assignee": "Ada"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Chase missing invoice"
    assert body["due_date"] == "2026-08-01"
    assert body["assignee"] == "Ada"
    assert body["source"] == "manual"
    assert body["status"] == "open"
    assert body["recurrence_rule"] is None


async def test_create_task_rejects_invalid_recurrence_rule(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/tasks",
        headers=headers,
        json={"title": "Quarterly review", "due_date": "2026-08-01", "recurrence_rule": "yearly"},
    )

    assert response.status_code == 400


async def test_create_task_rejects_recurrence_without_due_date(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/tasks", headers=headers, json={"title": "Quarterly review", "recurrence_rule": "monthly"}
    )

    assert response.status_code == 400


async def test_create_task_requires_auth(client):
    response = await client.post("/tasks", json={"title": "Unauthorized task"})
    assert response.status_code == 401


async def test_completing_a_recurring_task_creates_the_next_occurrence(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/tasks",
        headers=headers,
        json={"title": "Weekly status update stu888", "due_date": "2026-07-06", "recurrence_rule": "weekly"},
    )
    task_id = created.json()["id"]

    response = await client.patch(f"/tasks/{task_id}", headers=headers, json={"status": "done"})
    assert response.status_code == 200
    assert response.json()["status"] == "done"

    all_open = await client.get("/tasks", params={"status": "open", "limit": 200}, headers=headers)
    next_occurrence = [
        t for t in all_open.json() if t["title"] == "Weekly status update stu888" and t["id"] != task_id
    ]
    assert len(next_occurrence) == 1
    assert next_occurrence[0]["due_date"] == "2026-07-13"
    assert next_occurrence[0]["recurrence_rule"] == "weekly"


async def test_completing_a_one_time_task_does_not_create_a_new_occurrence(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/tasks", headers=headers, json={"title": "One-off cleanup task xyz123"})
    task_id = created.json()["id"]

    await client.patch(f"/tasks/{task_id}", headers=headers, json={"status": "done"})

    all_tasks = await client.get("/tasks", params={"status": "open", "limit": 200}, headers=headers)
    matches = [t for t in all_tasks.json() if t["title"] == "One-off cleanup task xyz123"]
    assert len(matches) == 0


async def test_editing_due_date_clears_notified_at(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/tasks", headers=headers, json={"title": "Renew APK", "due_date": "2026-07-15"}
    )
    task_id = created.json()["id"]

    response = await client.patch(
        f"/tasks/{task_id}", headers=headers, json={"status": "open", "due_date": "2026-07-20"}
    )
    assert response.status_code == 200
    assert response.json()["due_date"] == "2026-07-20"
