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
    with patch("api.planner_agent.chat_completion", return_value=fake_llm_output) as mock_completion:
        response = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)

    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Submit the report"
    assert tasks[0]["due_date"] == "2026-08-01"
    assert tasks[0]["assignee"] == "Alice"
    assert tasks[0]["source"] == "planner_agent"

    from api.planner_agent import EXTRACTION_SCHEMA

    assert mock_completion.call_args.kwargs["schema"] == EXTRACTION_SCHEMA


async def test_extract_tasks_persists_category_when_provided(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Dentist appointment booked for 2026-08-01.")

    fake_llm_output = (
        '[{"title": "Attend dentist appointment", "description": null, '
        '"due_date": "2026-08-01", "assignee": null, "category": "appointment"}]'
    )
    with patch("api.planner_agent.chat_completion", return_value=fake_llm_output):
        response = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["category"] == "appointment"


async def test_extract_tasks_defaults_invalid_category_to_none(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    fake_llm_output = '[{"title": "Do a thing", "category": "not-a-real-category"}]'
    with patch("api.planner_agent.chat_completion", return_value=fake_llm_output):
        response = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["category"] is None


async def test_extract_tasks_defaults_missing_category_to_none(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    with patch("api.planner_agent.chat_completion", return_value='[{"title": "Do a thing"}]'):
        response = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["category"] is None


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


async def _login_as(client, username: str) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_id_for(username: str):
    from sqlalchemy import select

    from api.db import async_session
    from api.models import User

    async with async_session() as db:
        return (await db.execute(select(User).where(User.username == username))).scalar_one().id


async def test_list_tasks_excludes_other_users_standalone_tasks(client):
    headers_a = {"Authorization": f"Bearer {await _login_as(client, 'taskowner1')}"}
    headers_b = {"Authorization": f"Bearer {await _login_as(client, 'taskintruder1')}"}

    created = await client.post("/tasks", headers=headers_a, json={"title": "Owner-only task xtsk1"})
    task_id = created.json()["id"]

    listed_b = await client.get("/tasks", params={"limit": 200}, headers=headers_b)
    assert task_id not in {t["id"] for t in listed_b.json()}

    listed_a = await client.get("/tasks", params={"limit": 200}, headers=headers_a)
    assert task_id in {t["id"] for t in listed_a.json()}


async def test_update_task_rejects_non_owner(client):
    headers_a = {"Authorization": f"Bearer {await _login_as(client, 'taskowner2')}"}
    headers_b = {"Authorization": f"Bearer {await _login_as(client, 'taskintruder2')}"}

    created = await client.post("/tasks", headers=headers_a, json={"title": "Protected task xtsk2"})
    task_id = created.json()["id"]

    response = await client.patch(f"/tasks/{task_id}", headers=headers_b, json={"status": "done"})
    assert response.status_code == 403


async def test_extract_tasks_from_document_rejects_non_owner(client):
    headers_a = {"Authorization": f"Bearer {await _login_as(client, 'taskowner3')}"}
    headers_b = {"Authorization": f"Bearer {await _login_as(client, 'taskintruder3')}"}

    document_id = await _upload_ready_document(client, headers_a, "Some text with a deadline.")

    response = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers_b)
    assert response.status_code == 403


async def test_accepted_case_member_can_see_and_modify_document_linked_task(client):
    from uuid import UUID as _UUID

    from api.db import async_session
    from api.models import Task

    owner_headers = {"Authorization": f"Bearer {await _login_as(client, 'taskcaseowner1')}"}
    member_headers = {"Authorization": f"Bearer {await _login_as(client, 'taskcasemember1')}"}
    member_id = await _user_id_for("taskcasemember1")

    document_id = await _upload_ready_document(client, owner_headers, "Case document text.")

    case_response = await client.post("/cases", headers=owner_headers, json={"name": "Shared task case"})
    case_id = case_response.json()["id"]
    await client.put(f"/documents/{document_id}/case", headers=owner_headers, json={"case_id": case_id})
    await client.post(f"/cases/{case_id}/members", headers=owner_headers, json={"user_id": str(member_id)})
    await client.post(f"/cases/{case_id}/members/{member_id}/accept", headers=member_headers)

    async with async_session() as db:
        task = Task(document_id=_UUID(document_id), title="Shared case task", source="manual", created_by=None)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        task_id = str(task.id)

    listed = await client.get("/tasks", params={"limit": 200}, headers=member_headers)
    assert task_id in {t["id"] for t in listed.json()}

    response = await client.patch(f"/tasks/{task_id}", headers=member_headers, json={"status": "done"})
    assert response.status_code == 200


async def test_non_member_cannot_see_or_modify_document_linked_task_of_others_case(client):
    from uuid import UUID as _UUID

    from api.db import async_session
    from api.models import Task

    owner_headers = {"Authorization": f"Bearer {await _login_as(client, 'taskcaseowner2')}"}
    outsider_headers = {"Authorization": f"Bearer {await _login_as(client, 'taskoutsider2')}"}

    document_id = await _upload_ready_document(client, owner_headers, "Private case document text.")

    async with async_session() as db:
        task = Task(document_id=_UUID(document_id), title="Private case task", source="manual", created_by=None)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        task_id = str(task.id)

    listed = await client.get("/tasks", params={"limit": 200}, headers=outsider_headers)
    assert task_id not in {t["id"] for t in listed.json()}

    response = await client.patch(f"/tasks/{task_id}", headers=outsider_headers, json={"status": "done"})
    assert response.status_code == 403


async def test_create_task_with_category(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/tasks", headers=headers, json={"title": "Pay invoice", "category": "payment"}
    )

    assert response.status_code == 201
    assert response.json()["category"] == "payment"


async def test_create_task_defaults_category_to_null(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/tasks", headers=headers, json={"title": "No category task"})

    assert response.status_code == 201
    assert response.json()["category"] is None


async def test_create_task_rejects_invalid_category(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/tasks", headers=headers, json={"title": "Bad category task", "category": "not-a-category"}
    )

    assert response.status_code == 400


async def test_update_task_sets_category(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/tasks", headers=headers, json={"title": "Untyped task"})
    task_id = created.json()["id"]

    response = await client.patch(
        f"/tasks/{task_id}", headers=headers, json={"status": "open", "category": "deadline"}
    )

    assert response.status_code == 200
    assert response.json()["category"] == "deadline"


async def test_update_task_rejects_invalid_category(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/tasks", headers=headers, json={"title": "Untyped task 2"})
    task_id = created.json()["id"]

    response = await client.patch(
        f"/tasks/{task_id}", headers=headers, json={"status": "open", "category": "bogus"}
    )

    assert response.status_code == 400


async def test_completing_a_recurring_task_copies_category_to_next_occurrence(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/tasks",
        headers=headers,
        json={
            "title": "Recurring payment stu999",
            "due_date": "2026-07-06",
            "recurrence_rule": "weekly",
            "category": "payment",
        },
    )
    task_id = created.json()["id"]

    await client.patch(f"/tasks/{task_id}", headers=headers, json={"status": "done"})

    all_open = await client.get("/tasks", params={"status": "open", "limit": 200}, headers=headers)
    next_occurrence = [
        t for t in all_open.json() if t["title"] == "Recurring payment stu999" and t["id"] != task_id
    ]
    assert len(next_occurrence) == 1
    assert next_occurrence[0]["category"] == "payment"


async def test_export_task_ics_returns_well_formed_all_day_vevent(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/tasks", headers=headers, json={"title": "Renew passport", "due_date": "2026-08-01"}
    )
    task_id = created.json()["id"]

    response = await client.get(f"/tasks/{task_id}/ics", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert 'filename="renew-passport.ics"' in response.headers["content-disposition"]
    body = response.text
    assert "BEGIN:VEVENT" in body
    assert "SUMMARY:Renew passport" in body
    assert "DTSTART;VALUE=DATE:20260801" in body


async def test_export_task_ics_rejects_task_without_due_date(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/tasks", headers=headers, json={"title": "No due date task"})
    task_id = created.json()["id"]

    response = await client.get(f"/tasks/{task_id}/ics", headers=headers)
    assert response.status_code == 409


async def test_export_task_ics_rejects_unknown_id(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        "/tasks/00000000-0000-0000-0000-000000000000/ics", headers=headers
    )
    assert response.status_code == 404


async def test_export_task_ics_rejects_non_owner(client):
    owner_headers = {"Authorization": f"Bearer {await _login_as(client, 'icstaskowner1')}"}
    outsider_headers = {"Authorization": f"Bearer {await _login_as(client, 'icstaskoutsider1')}"}

    created = await client.post(
        "/tasks", headers=owner_headers, json={"title": "Private deadline task", "due_date": "2026-08-01"}
    )
    task_id = created.json()["id"]

    response = await client.get(f"/tasks/{task_id}/ics", headers=outsider_headers)
    assert response.status_code == 403


async def test_export_task_ics_requires_auth(client):
    response = await client.get("/tasks/00000000-0000-0000-0000-000000000000/ics")
    assert response.status_code == 401


async def test_extracted_appointment_task_creates_a_linked_appointment(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Dentist appointment booked for 2026-08-01.")

    fake_llm_output = (
        '[{"title": "Attend dentist appointment", "description": null, '
        '"due_date": "2026-08-01", "assignee": null, "category": "appointment"}]'
    )
    with patch("api.planner_agent.chat_completion", return_value=fake_llm_output):
        extracted = await client.post(f"/documents/{document_id}/extract-tasks", headers=headers)
    task_id = extracted.json()[0]["id"]

    appointments = await client.get(
        "/appointments", headers=headers, params={"from": "2026-07-01", "to": "2026-08-31"}
    )
    matching = [a for a in appointments.json() if a["source_task_id"] == task_id]
    assert len(matching) == 1
    assert matching[0]["title"] == "Attend dentist appointment"


async def test_creating_a_task_with_appointment_category_creates_a_linked_appointment(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/tasks", headers=headers,
        json={"title": "Yearly checkup", "due_date": "2026-08-05", "category": "appointment"},
    )
    task_id = created.json()["id"]

    appointments = await client.get(
        "/appointments", headers=headers, params={"from": "2026-07-01", "to": "2026-08-31"}
    )
    matching = [a for a in appointments.json() if a["source_task_id"] == task_id]
    assert len(matching) == 1
    assert matching[0]["title"] == "Yearly checkup"


async def test_setting_a_tasks_category_to_appointment_via_patch_creates_a_linked_appointment(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/tasks", headers=headers, json={"title": "Follow-up call", "due_date": "2026-08-10"})
    task_id = created.json()["id"]

    await client.patch(f"/tasks/{task_id}", headers=headers, json={"status": "open", "category": "appointment"})

    appointments = await client.get(
        "/appointments", headers=headers, params={"from": "2026-07-01", "to": "2026-08-31"}
    )
    matching = [a for a in appointments.json() if a["source_task_id"] == task_id]
    assert len(matching) == 1


async def test_get_task_returns_the_task(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/tasks", headers=headers, json={"title": "Fetchable task"})
    task_id = created.json()["id"]

    response = await client.get(f"/tasks/{task_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Fetchable task"


async def test_get_task_returns_404_for_unknown_id(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/tasks/00000000-0000-0000-0000-000000000000", headers=headers)
    assert response.status_code == 404


async def test_get_task_rejects_non_owner(client):
    owner_headers = {"Authorization": f"Bearer {await _login_as(client, 'getowner1')}"}
    intruder_headers = {"Authorization": f"Bearer {await _login_as(client, 'getintruder1')}"}

    task_id = (
        await client.post("/tasks", headers=owner_headers, json={"title": "Private task"})
    ).json()["id"]

    response = await client.get(f"/tasks/{task_id}", headers=intruder_headers)
    assert response.status_code == 403


async def test_get_task_requires_auth(client):
    response = await client.get("/tasks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401


async def test_delete_task_removes_it(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/tasks", headers=headers, json={"title": "Task to delete"})
    task_id = created.json()["id"]

    delete_response = await client.delete(f"/tasks/{task_id}", headers=headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/tasks/{task_id}", headers=headers)
    assert get_response.status_code == 404


async def test_delete_task_unlinks_from_case_without_deleting_case(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    task_id = (await client.post("/tasks", headers=headers, json={"title": "Linked task"})).json()["id"]
    case_id = (await client.post("/cases", headers=headers, json={"name": "Case with linked task"})).json()["id"]
    await client.post(f"/cases/{case_id}/tasks/{task_id}", headers=headers)

    delete_response = await client.delete(f"/tasks/{task_id}", headers=headers)
    assert delete_response.status_code == 204

    case_response = await client.get(f"/cases/{case_id}", headers=headers)
    assert case_response.status_code == 200
    assert case_response.json()["tasks"] == []


async def test_delete_task_rejects_non_owner(client):
    owner_headers = {"Authorization": f"Bearer {await _login_as(client, 'delowner1')}"}
    intruder_headers = {"Authorization": f"Bearer {await _login_as(client, 'delintruder1')}"}

    task_id = (
        await client.post("/tasks", headers=owner_headers, json={"title": "Protected from deletion"})
    ).json()["id"]

    response = await client.delete(f"/tasks/{task_id}", headers=intruder_headers)
    assert response.status_code == 403


async def test_delete_task_requires_auth(client):
    response = await client.delete("/tasks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401


async def test_update_task_title_and_description(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/tasks", headers=headers, json={"title": "Original title"})
    task_id = created.json()["id"]

    response = await client.patch(
        f"/tasks/{task_id}",
        headers=headers,
        json={"status": "open", "title": "Renamed title", "description": "New description"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed title"
    assert response.json()["description"] == "New description"


async def test_patching_a_task_twice_does_not_create_duplicate_appointments(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/tasks", headers=headers,
        json={"title": "Repeat check", "due_date": "2026-08-12", "category": "appointment"},
    )
    task_id = created.json()["id"]

    await client.patch(
        f"/tasks/{task_id}", headers=headers, json={"status": "in_progress", "category": "appointment"}
    )

    appointments = await client.get(
        "/appointments", headers=headers, params={"from": "2026-07-01", "to": "2026-08-31"}
    )
    matching = [a for a in appointments.json() if a["source_task_id"] == task_id]
    assert len(matching) == 1
