from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Residency, User
from sqlalchemy import select

FAKE_EMBEDDING = [0.1] * 768
FAKE_CLASSIFICATION = (
    '{"doc_type": "contract", "tags": ["nda"], "confidence": 0.9, '
    '"correspondent": {"name": "Beacon Inc", "street": "Market St", "house_number": "1", '
    '"po_box": null, "postal_code": "94103", "city": "San Francisco", "country": "USA"}}'
)
FAKE_IDENTITY_CLASSIFICATION = (
    '{"doc_type": "identity_document", "tags": [], "confidence": 0.9, '
    '"correspondent": {"name": null, "street": null, "house_number": null, '
    '"po_box": null, "postal_code": null, "city": null, "country": null}}'
)
FAKE_ADDRESS_EXTRACTION = (
    '{"entities": [{"name": "Herengracht 1, Amsterdam", "type": "address", '
    '"street": "Herengracht", "house_number": "1", "postal_code": "1011AA", '
    '"city": "Amsterdam", "country": "NL"}], "relationships": []}'
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


async def test_residency_detected_after_classification_despite_extraction_running_first(client):
    """Regression test for the actual production bug (see entity_agent.py's
    module docstring): `_handle_extract_entities` is registered before
    `_handle_classify_document` for the same `EmbeddingsCreated` event, so
    entity extraction -- and residency detection's `category_id` gate --
    normally runs while `category_id` is still NULL. This drives the real
    event chain (no shortcuts calling entity_agent/document_classification
    functions directly) to prove `_handle_reconcile_residency`
    (DOCUMENT_CLASSIFIED subscriber) actually catches this up end-to-end,
    once classification succeeds."""
    # Unique per run -- this suite shares one persistent DB with no per-test
    # rollback (see test_residencies.py), so a fixed username would pick up
    # a stale residency from a previous run instead of the one this test
    # just created.
    username = f"residencyeventuser-{uuid4().hex[:8]}"
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-residency"),
        patch("api.documents.wait_for_paperless_id", return_value=54321),
        patch("api.documents.fetch_document_text", return_value="Identity document text."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.entity_agent.chat_completion", AsyncMock(return_value=FAKE_ADDRESS_EXTRACTION)),
        patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_IDENTITY_CLASSIFICATION)),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_extract_metafields_on_ready", False),
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("id.txt", b"id card", "text/plain")}
        )
    document_id = upload.json()["id"]

    detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert detail.json()["doc_type"] == "identity_document"

    async with async_session() as db:
        user_result = await db.execute(select(User).where(User.username == username))
        user = user_result.scalar_one()
        residency_result = await db.execute(
            select(Residency).where(Residency.user_id == user.id, Residency.valid_to.is_(None))
        )
        residency = residency_result.scalar_one_or_none()

    assert residency is not None
    assert str(residency.source_document_id) == document_id
