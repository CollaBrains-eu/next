"""Metafield .ics export -- lets a user download a calendar event for any
date-typed extracted metafield (e.g. an invoice's due_date), without requiring
the full calendar-sync sub-project. Documents are created directly via the ORM
with metafields already set, same rationale as test_document_access_control.py:
the upload pipeline's LLM calls aren't relevant here.
"""
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Document, User


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_id(username: str) -> UUID:
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one().id


async def _create_document(owner_id: UUID, title: str, *, doc_type: str | None, metafields: dict | None) -> UUID:
    document_id = uuid4()
    async with async_session() as db:
        db.add(
            Document(
                id=document_id, owner_id=owner_id, title=title, filename=f"{title}.txt",
                mime_type="text/plain", status="ready", doc_type=doc_type, metafields=metafields,
            )
        )
        await db.commit()
    return document_id


async def test_export_metafield_ics_returns_well_formed_all_day_vevent(client):
    token = await _login(client, "icsmetauser1")
    headers = {"Authorization": f"Bearer {token}"}
    owner_id = await _user_id("icsmetauser1")
    document_id = await _create_document(
        owner_id, "Electric bill", doc_type="invoice",
        metafields={"amount": "120.00", "due_date": "2026-08-01", "invoice_number": "INV-9"},
    )

    response = await client.get(f"/documents/{document_id}/metafields/due_date/ics", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    body = response.text
    assert "BEGIN:VEVENT" in body
    assert "DTSTART;VALUE=DATE:20260801" in body


async def test_export_metafield_ics_rejects_non_date_field(client):
    token = await _login(client, "icsmetauser2")
    headers = {"Authorization": f"Bearer {token}"}
    owner_id = await _user_id("icsmetauser2")
    document_id = await _create_document(
        owner_id, "Electric bill", doc_type="invoice",
        metafields={"amount": "120.00", "due_date": "2026-08-01", "invoice_number": "INV-9"},
    )

    response = await client.get(f"/documents/{document_id}/metafields/amount/ics", headers=headers)
    assert response.status_code == 409


async def test_export_metafield_ics_rejects_field_with_no_value(client):
    token = await _login(client, "icsmetauser3")
    headers = {"Authorization": f"Bearer {token}"}
    owner_id = await _user_id("icsmetauser3")
    document_id = await _create_document(owner_id, "Electric bill", doc_type="invoice", metafields={})

    response = await client.get(f"/documents/{document_id}/metafields/due_date/ics", headers=headers)
    assert response.status_code == 409


async def test_export_metafield_ics_rejects_unknown_document(client):
    token = await _login(client, "icsmetauser4")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        "/documents/00000000-0000-0000-0000-000000000000/metafields/due_date/ics", headers=headers
    )
    assert response.status_code == 404


async def test_export_metafield_ics_rejects_non_owner(client):
    owner_token = await _login(client, "icsmetaowner1")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    owner_id = await _user_id("icsmetaowner1")
    document_id = await _create_document(
        owner_id, "Private invoice", doc_type="invoice", metafields={"due_date": "2026-08-01"},
    )

    outsider_token = await _login(client, "icsmetaoutsider1")
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    response = await client.get(f"/documents/{document_id}/metafields/due_date/ics", headers=outsider_headers)
    assert response.status_code == 403
