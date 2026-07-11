from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Task
from api.scripts.notify_due_tasks import notify_due_tasks


async def _login_and_link_phone(client, username: str, phone: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    token = response.json()["access_token"]
    await client.put("/auth/me/phone", headers={"Authorization": f"Bearer {token}"}, json={"phone_number": phone})
    return token


async def _task_by_title(title: str) -> Task:
    async with async_session() as db:
        result = await db.execute(select(Task).where(Task.title == title))
        return result.scalars().one()


async def test_notifies_creator_for_a_task_due_today(client):
    token = await _login_and_link_phone(client, "notifyuser1", "+15559990001")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/tasks", headers=headers, json={"title": "Due today task abc111", "due_date": date.today().isoformat()}
    )

    with patch("api.scripts.notify_due_tasks.send_signal_message", new=AsyncMock()) as mock_send:
        sent = await notify_due_tasks()

    assert sent >= 1
    matching_calls = [c for c in mock_send.call_args_list if c.args[0] == "+15559990001"]
    assert len(matching_calls) == 1
    assert "due today" in matching_calls[0].args[1]

    task = await _task_by_title("Due today task abc111")
    assert task.notified_at is not None


async def test_overdue_task_message_mentions_days_overdue(client):
    token = await _login_and_link_phone(client, "notifyuser2", "+15559990002")
    headers = {"Authorization": f"Bearer {token}"}
    overdue_date = (date.today() - timedelta(days=3)).isoformat()
    await client.post("/tasks", headers=headers, json={"title": "Overdue task xyz222", "due_date": overdue_date})

    with patch("api.scripts.notify_due_tasks.send_signal_message", new=AsyncMock()) as mock_send:
        await notify_due_tasks()

    matching_calls = [c for c in mock_send.call_args_list if c.args[0] == "+15559990002"]
    assert len(matching_calls) == 1
    assert "overdue by 3 day" in matching_calls[0].args[1]


async def test_does_not_renotify_an_already_notified_task(client):
    token = await _login_and_link_phone(client, "notifyuser3", "+15559990003")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/tasks", headers=headers, json={"title": "Already notified task def333", "due_date": date.today().isoformat()}
    )

    with patch("api.scripts.notify_due_tasks.send_signal_message", new=AsyncMock()):
        await notify_due_tasks()

    with patch("api.scripts.notify_due_tasks.send_signal_message", new=AsyncMock()) as second_run:
        await notify_due_tasks()

    matching_calls = [c for c in second_run.call_args_list if c.args[0] == "+15559990003"]
    assert len(matching_calls) == 0


async def test_skips_a_task_whose_creator_has_no_linked_phone(client):
    identity = LdapIdentity(username="nophoneuser", display_name="No Phone", email="nophoneuser@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "nophoneuser", "password": "whatever"})
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/tasks", headers=headers, json={"title": "No phone task ghi444", "due_date": date.today().isoformat()}
    )

    with patch("api.scripts.notify_due_tasks.send_signal_message", new=AsyncMock()) as mock_send:
        sent = await notify_due_tasks()

    task = await _task_by_title("No phone task ghi444")
    assert task.notified_at is None
    assert mock_send.call_count == sent  # this task contributed zero calls, whatever the batch total


async def test_future_due_task_is_not_notified(client):
    token = await _login_and_link_phone(client, "notifyuser5", "+15559990005")
    headers = {"Authorization": f"Bearer {token}"}
    future_date = (date.today() + timedelta(days=30)).isoformat()
    await client.post("/tasks", headers=headers, json={"title": "Future task jkl555", "due_date": future_date})

    with patch("api.scripts.notify_due_tasks.send_signal_message", new=AsyncMock()) as mock_send:
        await notify_due_tasks()

    matching_calls = [c for c in mock_send.call_args_list if c.args[0] == "+15559990005"]
    assert len(matching_calls) == 0


async def test_a_send_failure_does_not_block_the_rest_of_the_batch(client):
    token_a = await _login_and_link_phone(client, "notifyuser6a", "+15559990006")
    token_b = await _login_and_link_phone(client, "notifyuser6b", "+15559990007")
    await client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Failing send task mno666", "due_date": date.today().isoformat()},
    )
    await client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "Succeeding send task pqr777", "due_date": date.today().isoformat()},
    )

    async def flaky_send(phone: str, text: str) -> None:
        if phone == "+15559990006":
            raise RuntimeError("simulated Signal outage")

    with patch("api.scripts.notify_due_tasks.send_signal_message", new=AsyncMock(side_effect=flaky_send)):
        await notify_due_tasks()

    failing_task = await _task_by_title("Failing send task mno666")
    succeeding_task = await _task_by_title("Succeeding send task pqr777")
    assert failing_task.notified_at is None
    assert succeeding_task.notified_at is not None
