from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Decision, Document, Entity, Task, User, Vehicle


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
    assert body["appointments"] == []


async def test_case_dashboard_includes_appointments_linked_via_case_id(client):
    token = await _login(client, "caserouteruser27")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    appointment_response = await client.post(
        "/appointments", headers=headers, json={"title": "Deposition", "starts_at": "2026-08-01T13:00:00Z", "case_id": case_id}
    )
    appointment_id = appointment_response.json()["id"]

    dashboard = await client.get(f"/cases/{case_id}", headers=headers)
    assert [a["id"] for a in dashboard.json()["appointments"]] == [appointment_id]


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


async def _user_id_for(username: str):
    async with async_session() as db:
        return (await db.execute(select(User).where(User.username == username))).scalar_one().id


async def _create_document(owner_id) -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="t", filename="t.pdf", mime_type="application/pdf", status="ready",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def _create_task(created_by) -> Task:
    async with async_session() as db:
        task = Task(title="Do the thing", source="manual", created_by=created_by)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task


async def _create_decision(user_id) -> Decision:
    async with async_session() as db:
        decision = Decision(user_id=user_id, summary="Approved something")
        db.add(decision)
        await db.commit()
        await db.refresh(decision)
        return decision


async def test_attach_document_to_case_via_put(client):
    token = await _login(client, "caserouteruser14")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id_for("caserouteruser14")
    document = await _create_document(user_id)

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    put_response = await client.put(
        f"/documents/{document.id}/case", headers=headers, json={"case_id": case_id}
    )
    assert put_response.status_code == 200

    dashboard = await client.get(f"/cases/{case_id}", headers=headers)
    assert [d["id"] for d in dashboard.json()["documents"]] == [str(document.id)]


async def test_attach_document_rejects_non_owner_document(client):
    await _login(client, "caserouteruser15")
    intruder_token = await _login(client, "caserouteruser16")
    owner_id = await _user_id_for("caserouteruser15")
    document = await _create_document(owner_id)

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {intruder_token}"}, json={"name": "Intruder's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.put(
        f"/documents/{document.id}/case",
        headers={"Authorization": f"Bearer {intruder_token}"}, json={"case_id": case_id},
    )
    assert response.status_code == 403


async def test_link_task_to_case(client):
    token = await _login(client, "caserouteruser17")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id_for("caserouteruser17")
    task = await _create_task(user_id)

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    link_response = await client.post(f"/cases/{case_id}/tasks/{task.id}", headers=headers)
    assert link_response.status_code == 204

    dashboard = await client.get(f"/cases/{case_id}", headers=headers)
    assert [t["id"] for t in dashboard.json()["tasks"]] == [str(task.id)]


async def test_link_task_rejects_non_owner_task(client):
    await _login(client, "caserouteruser18")
    intruder_token = await _login(client, "caserouteruser19")
    owner_id = await _user_id_for("caserouteruser18")
    task = await _create_task(owner_id)

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {intruder_token}"}, json={"name": "Intruder's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.post(
        f"/cases/{case_id}/tasks/{task.id}", headers={"Authorization": f"Bearer {intruder_token}"}
    )
    assert response.status_code == 403


async def test_link_decision_to_case(client):
    token = await _login(client, "caserouteruser20")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id_for("caserouteruser20")
    decision = await _create_decision(user_id)

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    link_response = await client.post(f"/cases/{case_id}/decisions/{decision.id}", headers=headers)
    assert link_response.status_code == 204

    dashboard = await client.get(f"/cases/{case_id}", headers=headers)
    assert [d["id"] for d in dashboard.json()["decisions"]] == [str(decision.id)]


async def _create_vehicle_router(kenteken: str, owner_id) -> Vehicle:
    async with async_session() as db:
        entity = Entity(name=kenteken, entity_type="vehicle", owner_id=owner_id)
        db.add(entity)
        await db.flush()
        vehicle = Vehicle(entity_id=entity.id, kenteken=kenteken)
        db.add(vehicle)
        await db.commit()
        await db.refresh(vehicle)
        return vehicle


async def test_link_vehicle_to_case(client):
    token = await _login(client, "caserouteruser21")
    headers = {"Authorization": f"Bearer {token}"}
    owner_id = await _user_id_for("caserouteruser21")
    vehicle = await _create_vehicle_router(f"LV-{uuid4().hex[:2].upper()}-ST", owner_id)

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    link_response = await client.post(f"/cases/{case_id}/vehicles/{vehicle.id}", headers=headers)
    assert link_response.status_code == 204

    dashboard = await client.get(f"/cases/{case_id}", headers=headers)
    assert [v["id"] for v in dashboard.json()["vehicles"]] == [str(vehicle.id)]


async def test_link_vehicle_to_case_rejects_unknown_vehicle(client):
    token = await _login(client, "caserouteruser22")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    response = await client.post(f"/cases/{case_id}/vehicles/{uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_link_vehicle_rejects_non_owner_vehicle(client):
    await _login(client, "caserouteruser23")
    intruder_token = await _login(client, "caserouteruser24")
    owner_id = await _user_id_for("caserouteruser23")
    vehicle = await _create_vehicle_router(f"LV-{uuid4().hex[:2].upper()}-ST", owner_id)

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {intruder_token}"}, json={"name": "Intruder's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.post(
        f"/cases/{case_id}/vehicles/{vehicle.id}", headers={"Authorization": f"Bearer {intruder_token}"}
    )
    assert response.status_code == 403


async def test_export_cases_csv_only_includes_the_callers_own(client):
    token_a = await _login(client, "casecsvuser1")
    token_b = await _login(client, "casecsvuser2")

    await client.post("/cases", headers={"Authorization": f"Bearer {token_a}"}, json={"name": "A's case"})
    await client.post("/cases", headers={"Authorization": f"Bearer {token_b}"}, json={"name": "B's case"})

    response = await client.get("/cases/export.csv", headers={"Authorization": f"Bearer {token_a}"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    body = response.text
    assert body.splitlines()[0] == "id,name,description,status,created_at"
    assert "A's case" in body
    assert "B's case" not in body


async def test_export_cases_csv_requires_auth(client):
    response = await client.get("/cases/export.csv")
    assert response.status_code == 401
