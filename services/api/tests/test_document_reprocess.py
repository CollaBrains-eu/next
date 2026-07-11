from unittest.mock import patch
from uuid import uuid4

from api.ldap_auth import LdapIdentity

FAKE_EMBEDDING = [0.1] * 768


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _login(client, username: str, *, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _upload_and_fail_during_embedding(client, headers: dict) -> str:
    """Simulates a document that made it to Paperless (has a paperless_id)
    but then failed -- the only case a reprocess is meaningful for."""
    with (
        patch("api.documents.submit_document", return_value="task-reprocess"),
        patch("api.documents.wait_for_paperless_id", return_value=9001),
        patch("api.documents.fetch_document_text", return_value="Original text."),
        patch("api.documents.embed_text", side_effect=RuntimeError("ollama down")),
    ):
        response = await client.post(
            "/documents", headers=headers, files={"file": ("failed.txt", b"content", "text/plain")}
        )
    document_id = response.json()["id"]
    detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert detail.json()["status"] == "failed"
    return document_id


async def test_reprocess_requires_admin_role(client):
    username = _unique("reprocessmember")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_and_fail_during_embedding(client, headers)

    response = await client.post(f"/admin/documents/{document_id}/reprocess", headers=headers)
    assert response.status_code == 403


async def test_reprocess_unknown_document_returns_404(client):
    admin_token = await _login(client, _unique("reprocess404admin"), is_admin=True)
    response = await client.post(
        f"/admin/documents/{uuid4()}/reprocess", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


async def test_reprocess_document_without_paperless_id_returns_409(client):
    username = _unique("reprocessnopaperless")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    with patch("api.documents.submit_document", side_effect=RuntimeError("paperless unreachable")):
        response = await client.post(
            "/documents", headers=headers, files={"file": ("nostore.txt", b"content", "text/plain")}
        )
    document_id = response.json()["id"]

    admin_token = await _login(client, _unique("reprocessnopaperlessadmin"), is_admin=True)
    reprocess = await client.post(
        f"/admin/documents/{document_id}/reprocess", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert reprocess.status_code == 409


async def test_reprocess_already_ready_document_returns_409(client):
    username = _unique("reprocessready")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    with (
        patch("api.documents.submit_document", return_value="task-ready"),
        patch("api.documents.wait_for_paperless_id", return_value=9002),
        patch("api.documents.fetch_document_text", return_value="All good."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
    ):
        response = await client.post(
            "/documents", headers=headers, files={"file": ("ready.txt", b"content", "text/plain")}
        )
    document_id = response.json()["id"]

    admin_token = await _login(client, _unique("reprocessreadyadmin"), is_admin=True)
    reprocess = await client.post(
        f"/admin/documents/{document_id}/reprocess", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert reprocess.status_code == 409


async def test_reprocess_retries_a_failed_document_to_ready(client):
    username = _unique("reprocesshappy")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_and_fail_during_embedding(client, headers)

    admin_token = await _login(client, _unique("reprocesshappyadmin"), is_admin=True)
    with (
        patch("api.documents.fetch_document_text", return_value="Recovered text after retry."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
    ):
        reprocess = await client.post(
            f"/admin/documents/{document_id}/reprocess", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert reprocess.status_code == 202
    assert reprocess.json()["status"] == "reprocess_queued"

    detail = await client.get(f"/documents/{document_id}", headers=headers)
    body = detail.json()
    assert body["status"] == "ready"
    assert body["error"] is None
    assert body["ocr_text"] == "Recovered text after retry."
    assert body["chunk_count"] == 1


async def test_reprocess_replaces_old_chunks_not_append_to_them(client):
    from sqlalchemy import select

    from api.db import async_session
    from api.models import DocumentChunk

    username = _unique("reprocesschunks")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_and_fail_during_embedding(client, headers)

    admin_token = await _login(client, _unique("reprocesschunksadmin"), is_admin=True)
    long_text = " ".join(f"word{i}" for i in range(400))
    with (
        patch("api.documents.fetch_document_text", return_value=long_text),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
    ):
        await client.post(
            f"/admin/documents/{document_id}/reprocess", headers={"Authorization": f"Bearer {admin_token}"}
        )

    async with async_session() as db:
        result = await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == document_id))
        chunks = result.scalars().all()
    assert len(chunks) >= 1
    assert all(chunk.content != "Original text." for chunk in chunks)
