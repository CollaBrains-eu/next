from unittest.mock import AsyncMock, patch

from api.ldap_auth import LdapIdentity

FAKE_EMBEDDING = [0.1] * 768
FAKE_CLASSIFICATION = (
    '{"doc_type": "invoice", "tags": ["btw"], "confidence": 0.9, '
    '"correspondent": {"name": "Acme BV", "street": null, "house_number": null, '
    '"po_box": null, "postal_code": null, "city": null, "country": null}}'
)
FAKE_OTHER_CLASSIFICATION = (
    '{"doc_type": "other", "tags": [], "confidence": 0.3, '
    '"correspondent": {"name": null, "street": null, "house_number": null, '
    '"po_box": null, "postal_code": null, "city": null, "country": null}}'
)
FAKE_METAFIELDS = '{"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123"}'


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_metafields_extracted_after_classification(client):
    token = await _login(client, "metafieldeventuser1")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value="Invoice #INV-123, total EUR 500.00, due 2026-08-15."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
        patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_CLASSIFICATION)),
        patch("api.document_metafields.chat_completion", AsyncMock(return_value=FAKE_METAFIELDS)),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("invoice.txt", b"invoice text", "text/plain")}
        )
        document_id = upload.json()["id"]

    detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["doc_type"] == "invoice"
    assert body["metafields"] == {"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123"}


async def test_metafields_skipped_when_auto_extract_metafields_disabled(client):
    token = await _login(client, "metafieldeventuser2")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value="Invoice #INV-123, total EUR 500.00."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
        patch("api.documents.settings.auto_extract_metafields_on_ready", False),
        patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_CLASSIFICATION)),
        patch("api.document_metafields.chat_completion", AsyncMock(return_value=FAKE_METAFIELDS)) as mock_call,
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("invoice2.txt", b"invoice text", "text/plain")}
        )
        document_id = upload.json()["id"]

    detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert detail.json()["metafields"] is None
    mock_call.assert_not_called()


async def test_metafields_not_extracted_when_doc_type_has_no_schema(client):
    token = await _login(client, "metafieldeventuser3")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value="Some unclassifiable text."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
        patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_OTHER_CLASSIFICATION)),
        patch("api.document_metafields.chat_completion", AsyncMock(return_value=FAKE_METAFIELDS)) as mock_call,
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("other.txt", b"other text", "text/plain")}
        )
        document_id = upload.json()["id"]

    detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert detail.json()["metafields"] is None
    mock_call.assert_not_called()
