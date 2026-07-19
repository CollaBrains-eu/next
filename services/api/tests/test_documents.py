from unittest.mock import patch

from api.ldap_auth import LdapIdentity

FAKE_EMBEDDING = [0.1] * 768


async def _login(client) -> str:
    identity = LdapIdentity(
        username="docuser", display_name="Doc User", email="docuser@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "docuser", "password": "whatever"})
    return response.json()["access_token"]


async def test_upload_processes_document_end_to_end(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="fake-task-id"),
        patch("api.documents.wait_for_paperless_id", return_value=42),
        patch("api.documents.fetch_document_text", return_value="Hello world, this is a test document."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
    ):
        upload = await client.post(
            "/documents",
            headers=headers,
            files={"file": ("note.txt", b"Hello world, this is a test document.", "text/plain")},
        )
        assert upload.status_code == 202
        document_id = upload.json()["id"]

        detail = await client.get(f"/documents/{document_id}", headers=headers)

    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "ready"
    assert body["chunk_count"] == 1
    assert "test document" in body["ocr_text"]


async def test_upload_marks_document_failed_on_paperless_error(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with patch("api.documents.submit_document", side_effect=RuntimeError("paperless unreachable")):
        upload = await client.post(
            "/documents",
            headers=headers,
            files={"file": ("note.txt", b"content", "text/plain")},
        )
        document_id = upload.json()["id"]

        detail = await client.get(f"/documents/{document_id}", headers=headers)

    assert detail.json()["status"] == "failed"
    assert "paperless unreachable" in detail.json()["error"]


async def test_search_ranks_matching_document_first(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-a"),
        patch("api.documents.wait_for_paperless_id", return_value=1),
        patch("api.documents.fetch_document_text", return_value="The quick brown fox jumps over the lazy dog."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
    ):
        await client.post(
            "/documents", headers=headers, files={"file": ("fox.txt", b"fox", "text/plain")}
        )

    with patch("api.search_service.embed_text", return_value=FAKE_EMBEDDING):
        results = await client.get("/search", params={"q": "fox"}, headers=headers)

    assert results.status_code == 200
    hits = results.json()
    assert len(hits) >= 1
    assert "fox" in hits[0]["content"]


async def test_upload_detects_document_language_and_populates_chunk_content_tsv(client):
    from sqlalchemy import select

    from api.db import async_session
    from api.models import Document, DocumentChunk

    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    dutch_text = (
        "Deze overeenkomst wordt aangegaan door en tussen de partijen met als "
        "doel de voorwaarden vast te stellen die hun voortdurende zakelijke "
        "relatie beheersen, met inbegrip van betalingsschema's."
    )

    with (
        patch("api.documents.submit_document", return_value="task-lang"),
        patch("api.documents.wait_for_paperless_id", return_value=3),
        patch("api.documents.fetch_document_text", return_value=dutch_text),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("overeenkomst.txt", b"x", "text/plain")}
        )
    document_id = upload.json()["id"]

    async with async_session() as db:
        document = await db.get(Document, document_id)
        assert document.language == "dutch"

        chunk = (
            await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == document_id))
        ).scalar_one()
        assert chunk.content_tsv is not None


async def test_delete_document_removes_it_from_listing(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-b"),
        patch("api.documents.wait_for_paperless_id", return_value=2),
        patch("api.documents.fetch_document_text", return_value="Disposable content."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("temp.txt", b"temp", "text/plain")}
        )
    document_id = upload.json()["id"]

    with patch("api.documents.paperless_delete", return_value=None):
        delete_response = await client.delete(f"/documents/{document_id}", headers=headers)
    assert delete_response.status_code == 204

    missing = await client.get(f"/documents/{document_id}", headers=headers)
    assert missing.status_code == 404


async def test_upload_rejects_missing_token(client):
    response = await client.post("/documents", files={"file": ("x.txt", b"x", "text/plain")})
    assert response.status_code == 401


async def test_search_rejects_missing_token(client):
    response = await client.get("/search", params={"q": "anything"})
    assert response.status_code == 401


async def test_summarize_caches_result_and_skips_second_llm_call(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-c"),
        patch("api.documents.wait_for_paperless_id", return_value=3),
        patch("api.documents.fetch_document_text", return_value="Some long policy text to summarize."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("policy.txt", b"policy", "text/plain")}
        )
    document_id = upload.json()["id"]

    with patch("api.documents.chat_completion", return_value="A short summary.") as mock_completion:
        first = await client.post(f"/documents/{document_id}/summarize", headers=headers)
        second = await client.post(f"/documents/{document_id}/summarize", headers=headers)

    assert first.status_code == 200
    assert first.json()["summary"] == "A short summary."
    assert second.json()["summary"] == "A short summary."
    mock_completion.assert_called_once()


async def test_process_document_notifies_owner_on_ready_when_phone_linked(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    await client.put("/auth/me/phone", headers=headers, json={"phone_number": "+15559990010"})

    with (
        patch("api.documents.submit_document", return_value="task-notify-1"),
        patch("api.documents.wait_for_paperless_id", return_value=101),
        patch("api.documents.fetch_document_text", return_value="Some content."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.send_signal_message") as mock_send,
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("note.txt", b"content", "text/plain")}
        )

    assert upload.status_code == 202
    mock_send.assert_called_once()
    call_args = mock_send.call_args.args
    assert call_args[0] == "+15559990010"
    assert "ready" in call_args[1]


async def test_process_document_skips_notification_when_no_phone_linked(client):
    from unittest.mock import patch as _patch
    from api.ldap_auth import LdapIdentity as _LdapIdentity

    identity = _LdapIdentity(
        username="nophoneuser", display_name="No Phone User", email="nophoneuser@collabrains.eu", is_admin=False
    )
    with _patch("api.auth.ldap_authenticate", return_value=identity):
        login = await client.post("/auth/token", data={"username": "nophoneuser", "password": "whatever"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-notify-2"),
        patch("api.documents.wait_for_paperless_id", return_value=102),
        patch("api.documents.fetch_document_text", return_value="Some content."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.send_signal_message") as mock_send,
    ):
        await client.post("/documents", headers=headers, files={"file": ("note.txt", b"content", "text/plain")})

    mock_send.assert_not_called()


async def test_process_document_notifies_owner_on_failure(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    await client.put("/auth/me/phone", headers=headers, json={"phone_number": "+15559990011"})

    with (
        patch("api.documents.submit_document", side_effect=RuntimeError("paperless down")),
        patch("api.documents.send_signal_message") as mock_send,
    ):
        await client.post("/documents", headers=headers, files={"file": ("note.txt", b"content", "text/plain")})

    mock_send.assert_called_once()
    call_args = mock_send.call_args.args
    assert call_args[0] == "+15559990011"
    assert "failed" in call_args[1]


async def test_upload_document_on_behalf_of_linked_phone_number(client):
    """Signal attachment uploads use get_effective_user the same way /chat does (ADR 0007)."""
    from api.auth import create_access_token
    from api.db import async_session
    from api.models import User

    await _login(client)  # ensures docuser exists
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    await client.put("/auth/me/phone", headers=headers, json={"phone_number": "+15559990012"})

    async with async_session() as db:
        db.add(User(username="test-signal-bot-upload", display_name="bot", role="service"))
        await db.commit()
    service_token = create_access_token("test-signal-bot-upload", "service")

    with (
        patch("api.documents.submit_document", return_value="task-notify-3"),
        patch("api.documents.wait_for_paperless_id", return_value=103),
        patch("api.documents.fetch_document_text", return_value="Some content."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.send_signal_message"),
    ):
        upload = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {service_token}", "X-On-Behalf-Of-Phone": "+15559990012"},
            files={"file": ("scan.pdf", b"content", "application/pdf")},
        )

    assert upload.status_code == 202

    from sqlalchemy import select
    from api.models import Document

    async with async_session() as db:
        result = await db.execute(select(Document).where(Document.id == upload.json()["id"]))
        document = result.scalar_one()
        result = await db.execute(select(User).where(User.username == "docuser"))
        docuser = result.scalar_one()
    assert document.owner_id == docuser.id


async def test_upload_document_on_behalf_of_rejects_unlinked_phone_number(client):
    from api.auth import create_access_token
    from api.db import async_session
    from api.models import User

    async with async_session() as db:
        db.add(User(username="test-signal-bot-upload-2", display_name="bot", role="service"))
        await db.commit()
    service_token = create_access_token("test-signal-bot-upload-2", "service")

    response = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {service_token}", "X-On-Behalf-Of-Phone": "+15559990099"},
        files={"file": ("scan.pdf", b"content", "application/pdf")},
    )
    assert response.status_code == 403


async def test_upload_triggers_vehicle_detection_and_creates_entity(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=101),
        patch("api.documents.fetch_document_text", return_value="Kenteken VE-01-HI staat geregistreerd."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.vehicle_agent.fetch_vehicle_data", return_value=None),
    ):
        upload = await client.post(
            "/documents", headers=headers,
            files={"file": ("vehicle.txt", b"Kenteken VE-01-HI staat geregistreerd.", "text/plain")},
        )

    assert upload.status_code == 202
    response = await client.get("/entities?entity_type=vehicle", headers=headers)
    names = {entity["name"] for entity in response.json()}
    assert "VE01HI" in names


async def test_list_documents_includes_classification_and_category_fields(client):
    from sqlalchemy import select

    from api.db import async_session
    from api.models import Category, Document, User

    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "docuser"))
        owner = result.scalar_one()
        result = await db.execute(select(Category).where(Category.category_type == "document").limit(1))
        category = result.scalar_one()
        document = Document(
            owner_id=owner.id, title="listcheck.pdf", filename="listcheck.pdf", mime_type="application/pdf",
            status="ready", doc_type="invoice", tags=["a", "b"], correspondent="Listcheck BV",
            category_id=category.id,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        document_id = str(document.id)

    response = await client.get("/documents", headers=headers)
    assert response.status_code == 200
    body = next(d for d in response.json() if d["id"] == document_id)
    assert body["doc_type"] == "invoice"
    assert body["tags"] == ["a", "b"]
    assert body["correspondent"] == "Listcheck BV"
    assert body["category_id"] == str(category.id)
