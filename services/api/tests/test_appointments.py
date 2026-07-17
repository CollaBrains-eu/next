from unittest.mock import patch

from api.ldap_auth import LdapIdentity


async def _login(client) -> str:
    identity = LdapIdentity(
        username="calendaruser", display_name="Calendar User", email="calendaruser@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "calendaruser", "password": "whatever"})
    return response.json()["access_token"]


async def test_create_appointment(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/appointments",
        headers=headers,
        json={"title": "APK inspection", "starts_at": "2026-07-14T09:30:00Z", "location": "RDW Keuringsstation, Arnhem"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "APK inspection"
    assert body["location"] == "RDW Keuringsstation, Arnhem"
    assert body["case_id"] is None
    assert body["vehicle_id"] is None


async def test_list_appointments_filters_by_date_range(client):
    # Uses September 2026 (not shared with any other test in this file) so
    # leftover rows from other tests' July 2026 appointments can't leak in --
    # this suite has no per-test DB cleanup, same as the rest of this project.
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post("/appointments", headers=headers, json={"title": "In range", "starts_at": "2026-09-14T09:30:00Z"})
    await client.post("/appointments", headers=headers, json={"title": "Out of range", "starts_at": "2026-10-01T09:30:00Z"})

    response = await client.get("/appointments", headers=headers, params={"from": "2026-09-01", "to": "2026-09-30"})

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == ["In range"]


async def test_list_appointments_requires_from_and_to(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/appointments", headers=headers)

    assert response.status_code == 422


async def test_update_appointment_edits_fields(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post(
        "/appointments", headers=headers, json={"title": "Original", "starts_at": "2026-07-14T09:30:00Z"}
    )
    appointment_id = create.json()["id"]

    response = await client.patch(
        f"/appointments/{appointment_id}", headers=headers, json={"title": "Updated", "location": "New spot"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Updated"
    assert body["location"] == "New spot"


async def test_update_appointment_rejects_unknown_id(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        "/appointments/00000000-0000-0000-0000-000000000000", headers=headers, json={"title": "x"}
    )

    assert response.status_code == 404


async def test_delete_appointment_removes_it(client):
    # November 2026: kept clear of every other test's date range in this file.
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post(
        "/appointments", headers=headers, json={"title": "To delete", "starts_at": "2026-11-14T09:30:00Z"}
    )
    appointment_id = create.json()["id"]

    delete_response = await client.delete(f"/appointments/{appointment_id}", headers=headers)
    assert delete_response.status_code == 204

    list_response = await client.get("/appointments", headers=headers, params={"from": "2026-11-01", "to": "2026-11-30"})
    assert list_response.json() == []


async def test_appointments_require_auth(client):
    response = await client.get("/appointments", params={"from": "2026-07-01", "to": "2026-07-31"})
    assert response.status_code == 401

    response = await client.post("/appointments", json={"title": "x", "starts_at": "2026-07-14T09:30:00Z"})
    assert response.status_code == 401
