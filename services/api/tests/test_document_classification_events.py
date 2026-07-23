from unittest.mock import AsyncMock, patch

from api.ldap_auth import LdapIdentity

FAKE_EMBEDDING = [0.1] * 768
FAKE_CLASSIFICATION = (
    '{"doc_type": "contract", "tags": ["nda"], "confidence": 0.9, '
    '"correspondent": {"name": "Beacon Inc", "street": "Market St", "house_number": "1", '
    '"po_box": null, "postal_code": "94103", "city": "San Francisco", "country": "USA"}}'
)


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_classification_triggers_after_embeddings_created(client):
    token = await _login(client, "classifyeventuser1")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value="This is an NDA with Beacon Inc."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        # Classification succeeds in this test (doc_type gets set), which fires
        # DOCUMENT_CLASSIFIED -> metafield extraction; facts extraction also
        # subscribes directly to EMBEDDINGS_CREATED. Neither is mocked, so
        # both need disabling or they hang on a real (unreachable) Ollama call.
        patch("api.documents.settings.auto_extract_metafields_on_ready", False),
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
        patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_CLASSIFICATION)),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("nda.txt", b"nda text", "text/plain")}
        )
        document_id = upload.json()["id"]

    detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["doc_type"] == "contract"
    assert body["tags"] == ["nda"]
    assert body["correspondent"] == "Beacon Inc"
    assert body["correspondent_street"] == "Market St"
    assert body["correspondent_house_number"] == "1"
    assert body["correspondent_po_box"] is None
    assert body["correspondent_postal_code"] == "94103"
    assert body["correspondent_city"] == "San Francisco"
    assert body["correspondent_country"] == "USA"


async def test_classification_skipped_when_auto_classify_disabled(client):
    token = await _login(client, "classifyeventuser2")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value="Some text"),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_classify_on_ready", False),
        # Facts extraction subscribes directly to EMBEDDINGS_CREATED (not
        # gated behind classification), so disabling auto_classify_on_ready
        # alone doesn't stop it -- unmocked, it hangs on a real Ollama call.
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
        patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_CLASSIFICATION)) as mock_call,
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("plain.txt", b"plain text", "text/plain")}
        )
        document_id = upload.json()["id"]

    detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert detail.json()["doc_type"] is None
    mock_call.assert_not_called()
