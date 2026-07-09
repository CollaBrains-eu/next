from unittest.mock import AsyncMock, patch

from api.ldap_auth import LdapIdentity

FAKE_EMBEDDING = [0.1] * 768
FAKE_EXTRACTION = (
    '{"facts": [{"fact_type": "employer", "value": "Beacon Inc", '
    '"valid_from": "2026-02-01", "valid_to": null, "confidence": 0.75}]}'
)


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_facts_extracted_after_embeddings_created(client):
    token = await _login(client, "factseventuser1")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value="Started at Beacon Inc in Feb 2026."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_classify_on_ready", False),
        patch("api.user_facts.chat_completion", AsyncMock(return_value=FAKE_EXTRACTION)),
    ):
        await client.post(
            "/documents", headers=headers, files={"file": ("job.txt", b"job text", "text/plain")}
        )

    facts = await client.get("/facts", headers=headers)
    assert facts.status_code == 200
    assert any(f["fact_type"] == "employer" and f["value"]["text"] == "Beacon Inc" for f in facts.json())


async def test_facts_extraction_skipped_when_disabled(client):
    token = await _login(client, "factseventuser2")
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
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
        patch("api.user_facts.chat_completion", AsyncMock(return_value=FAKE_EXTRACTION)) as mock_call,
    ):
        await client.post(
            "/documents", headers=headers, files={"file": ("plain.txt", b"plain text", "text/plain")}
        )

    mock_call.assert_not_called()
