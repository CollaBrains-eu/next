"""Owner-based access control for documents (list/get/search/chat/legal-draft).

Before this fix, list_documents/get_document had no ownership filter at
all (any authenticated user could see and read every user's documents),
and hybrid_search (backing /documents/search, /chat, and /legal/draft)
searched across every user's chunks unscoped -- /legal/draft's
caller-supplied `document_ids` could point at another user's document
with no ownership check (an IDOR). See ADR for this fix's own number.

Fixtures create Document/DocumentChunk rows directly via the ORM rather
than through POST /documents, since the upload endpoint's background
event chain (OCR -> embeddings -> auto task/entity/vehicle extraction)
makes real LLM calls that aren't mocked here and aren't relevant to
testing access control.
"""
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Document, DocumentChunk, User

FAKE_EMBEDDING = [0.1] * 768


async def _login(client, username: str, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_id(username: str) -> UUID:
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one().id


async def _create_document(
    owner_id: UUID, title: str, content: str, *, paperless_id: int | None = None
) -> UUID:
    document_id = uuid4()
    async with async_session() as db:
        db.add(
            Document(
                id=document_id, owner_id=owner_id, title=title, filename=f"{title}.txt",
                mime_type="text/plain", status="ready", paperless_id=paperless_id,
            )
        )
        db.add(DocumentChunk(document_id=document_id, chunk_index=0, content=content, embedding=FAKE_EMBEDDING))
        await db.commit()
    return document_id


async def test_list_documents_excludes_other_users_documents(client):
    owner_token = await _login(client, "accessowner1")
    owner_id = await _user_id("accessowner1")
    await _create_document(owner_id, "Owner's doc", "content")

    other_token = await _login(client, "accessother1")
    response = await client.get("/documents", headers={"Authorization": f"Bearer {other_token}"})

    assert response.status_code == 200
    assert response.json() == []

    own_response = await client.get("/documents", headers={"Authorization": f"Bearer {owner_token}"})
    assert len(own_response.json()) == 1


async def test_list_documents_admin_sees_all_documents(client):
    await _login(client, "accessowner2")
    owner_id = await _user_id("accessowner2")
    await _create_document(owner_id, "Someone's doc", "content")

    admin_token = await _login(client, "accessadmin1", is_admin=True)
    response = await client.get("/documents", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_get_document_forbidden_for_non_owner(client):
    await _login(client, "accessowner3")
    owner_id = await _user_id("accessowner3")
    document_id = await _create_document(owner_id, "Private doc", "content")

    other_token = await _login(client, "accessother3")
    response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {other_token}"})

    assert response.status_code == 403


async def test_get_document_allowed_for_owner(client):
    owner_token = await _login(client, "accessowner4")
    owner_id = await _user_id("accessowner4")
    document_id = await _create_document(owner_id, "My doc", "content")

    response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {owner_token}"})
    assert response.status_code == 200


async def test_get_document_admin_can_view_any_document(client):
    await _login(client, "accessowner5")
    owner_id = await _user_id("accessowner5")
    document_id = await _create_document(owner_id, "Someone's doc", "content")

    admin_token = await _login(client, "accessadmin2", is_admin=True)
    response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200


async def test_search_endpoint_only_returns_own_documents(client):
    await _login(client, "accessowner6")
    owner_id = await _user_id("accessowner6")
    await _create_document(owner_id, "Owner's report", "the quarterly report discusses revenue")

    other_token = await _login(client, "accessother6")
    with patch("api.search_service.embed_text", return_value=FAKE_EMBEDDING):
        response = await client.get(
            "/search", params={"q": "quarterly report"}, headers={"Authorization": f"Bearer {other_token}"}
        )

    assert response.status_code == 200
    assert response.json() == []


async def test_legal_draft_cannot_read_another_users_document_via_document_ids(client):
    """The IDOR this fix closes: previously, supplying another user's
    document_id in the request body was enough to have it retrieved and
    drafted from, with no ownership check anywhere in the path."""
    await _login(client, "accessowner7")
    owner_id = await _user_id("accessowner7")
    victim_document_id = await _create_document(
        owner_id, "Confidential settlement", "the settlement amount is $500,000, strictly confidential"
    )

    attacker_token = await _login(client, "accessattacker7")
    with (
        patch("api.search_service.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.legal.chat_completion", return_value="no context available") as mock_completion,
    ):
        response = await client.post(
            "/legal/draft",
            headers={"Authorization": f"Bearer {attacker_token}"},
            json={"instruction": "Summarize the settlement", "document_ids": [str(victim_document_id)]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["citations"] == []
    sent_context = mock_completion.call_args.args[0][1]["content"]
    assert "500,000" not in sent_context
    assert "no relevant documents found" in sent_context.lower()


async def test_chat_does_not_ground_answers_in_other_users_documents(client):
    await _login(client, "accessowner8")
    owner_id = await _user_id("accessowner8")
    await _create_document(owner_id, "Owner's medical record", "the patient's diagnosis is confidential")

    other_token = await _login(client, "accessother8")
    with (
        patch("api.search_service.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.chat.chat_completion", return_value="I don't have that information") as mock_completion,
        patch("api.chat.reflect") as mock_reflect,
    ):
        from api.reflection import ReflectionResult

        mock_reflect.return_value = ReflectionResult(sufficient_evidence=True, confidence=90, issues=[])
        response = await client.post(
            "/chat", headers={"Authorization": f"Bearer {other_token}"}, json={"message": "what is the diagnosis?"}
        )

    assert response.status_code == 200
    assert response.json()["citations"] == []
    sent_context = mock_completion.call_args.args[0][-1]["content"]
    assert "confidential" not in sent_context


async def test_get_document_file_forbidden_for_non_owner(client):
    await _login(client, "accessowner6")
    owner_id = await _user_id("accessowner6")
    document_id = await _create_document(owner_id, "Private file", "content", paperless_id=42)

    other_token = await _login(client, "accessother6")
    response = await client.get(
        f"/documents/{document_id}/file", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 403


async def test_get_document_file_allowed_for_owner(client):
    owner_token = await _login(client, "accessowner7")
    owner_id = await _user_id("accessowner7")
    document_id = await _create_document(owner_id, "My file", "content", paperless_id=42)

    with patch("api.documents.fetch_document_file", return_value=(b"%PDF-1.4 fake bytes", "application/pdf")):
        response = await client.get(
            f"/documents/{document_id}/file", headers={"Authorization": f"Bearer {owner_token}"}
        )

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake bytes"
    assert response.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="My file.txt"' in response.headers["content-disposition"]


async def test_get_document_file_admin_can_download_any_document(client):
    await _login(client, "accessowner8")
    owner_id = await _user_id("accessowner8")
    document_id = await _create_document(owner_id, "Someone's file", "content", paperless_id=99)

    admin_token = await _login(client, "accessadmin3", is_admin=True)
    with patch("api.documents.fetch_document_file", return_value=(b"bytes", "text/plain")):
        response = await client.get(
            f"/documents/{document_id}/file", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 200


async def test_get_document_file_supports_inline_disposition(client):
    owner_token = await _login(client, "accessowner9")
    owner_id = await _user_id("accessowner9")
    document_id = await _create_document(owner_id, "Inline file", "content", paperless_id=7)

    with patch("api.documents.fetch_document_file", return_value=(b"bytes", "application/pdf")):
        response = await client.get(
            f"/documents/{document_id}/file?disposition=inline",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("inline;")


async def test_get_document_file_404_when_paperless_id_missing(client):
    owner_token = await _login(client, "accessowner10")
    owner_id = await _user_id("accessowner10")
    document_id = await _create_document(owner_id, "Not yet processed", "content", paperless_id=None)

    response = await client.get(
        f"/documents/{document_id}/file", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 404


async def test_export_documents_csv_excludes_other_users_documents(client):
    owner_token = await _login(client, "csvowner1")
    owner_id = await _user_id("csvowner1")
    await _create_document(owner_id, "Owner's doc", "content")

    other_token = await _login(client, "csvother1")
    response = await client.get("/documents/export.csv", headers={"Authorization": f"Bearer {other_token}"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    body = response.text
    assert body.splitlines()[0] == "id,title,filename,status,doc_type,correspondent,tags,created_at,processed_at"
    assert "Owner's doc" not in body

    own_response = await client.get("/documents/export.csv", headers={"Authorization": f"Bearer {owner_token}"})
    assert "Owner's doc" in own_response.text


async def test_export_documents_csv_admin_sees_all_documents(client):
    await _login(client, "csvowner2")
    owner_id = await _user_id("csvowner2")
    await _create_document(owner_id, "Someone's doc", "content")

    admin_token = await _login(client, "csvadmin1", is_admin=True)
    response = await client.get("/documents/export.csv", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200
    assert "Someone's doc" in response.text


async def test_export_documents_csv_requires_auth(client):
    response = await client.get("/documents/export.csv")
    assert response.status_code == 401


async def test_accepted_case_member_can_read_and_download_a_case_linked_document(client):
    owner_token = await _login(client, "sharingowner1")
    owner_id = await _user_id("sharingowner1")
    document_id = await _create_document(owner_id, "Case doc", "content", paperless_id=11)

    case_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {owner_token}"}, json={"name": "Shared matter"}
    )
    case_id = case_response.json()["id"]
    await client.put(
        f"/documents/{document_id}/case", headers={"Authorization": f"Bearer {owner_token}"}, json={"case_id": case_id}
    )

    member_token = await _login(client, "sharingmember1")
    member_id = (await _user_id("sharingmember1"))
    await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"}, json={"user_id": str(member_id)}
    )
    await client.post(
        f"/cases/{case_id}/members/{member_id}/accept", headers={"Authorization": f"Bearer {member_token}"}
    )

    get_response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert get_response.status_code == 200

    with patch("api.documents.fetch_document_file", return_value=(b"bytes", "application/pdf")):
        file_response = await client.get(
            f"/documents/{document_id}/file", headers={"Authorization": f"Bearer {member_token}"}
        )
    assert file_response.status_code == 200


async def test_pending_case_member_cannot_read_a_case_linked_document(client):
    owner_token = await _login(client, "sharingowner2")
    owner_id = await _user_id("sharingowner2")
    document_id = await _create_document(owner_id, "Case doc", "content")

    case_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {owner_token}"}, json={"name": "Shared matter"}
    )
    case_id = case_response.json()["id"]
    await client.put(
        f"/documents/{document_id}/case", headers={"Authorization": f"Bearer {owner_token}"}, json={"case_id": case_id}
    )

    pending_token = await _login(client, "sharingpending1")
    pending_id = await _user_id("sharingpending1")
    await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"}, json={"user_id": str(pending_id)}
    )
    # deliberately not accepted

    response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {pending_token}"})
    assert response.status_code == 403


async def test_unrelated_user_still_cannot_read_a_case_linked_document(client):
    owner_token = await _login(client, "sharingowner3")
    owner_id = await _user_id("sharingowner3")
    document_id = await _create_document(owner_id, "Case doc", "content")

    case_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {owner_token}"}, json={"name": "Shared matter"}
    )
    case_id = case_response.json()["id"]
    await client.put(
        f"/documents/{document_id}/case", headers={"Authorization": f"Bearer {owner_token}"}, json={"case_id": case_id}
    )

    other_token = await _login(client, "sharingother1")
    response = await client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert response.status_code == 403


async def test_accepted_case_member_still_cannot_delete_the_document(client):
    owner_token = await _login(client, "sharingowner4")
    owner_id = await _user_id("sharingowner4")
    document_id = await _create_document(owner_id, "Case doc", "content")

    case_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {owner_token}"}, json={"name": "Shared matter"}
    )
    case_id = case_response.json()["id"]
    await client.put(
        f"/documents/{document_id}/case", headers={"Authorization": f"Bearer {owner_token}"}, json={"case_id": case_id}
    )

    member_token = await _login(client, "sharingmember4")
    member_id = await _user_id("sharingmember4")
    await client.post(
        f"/cases/{case_id}/members", headers={"Authorization": f"Bearer {owner_token}"}, json={"user_id": str(member_id)}
    )
    await client.post(
        f"/cases/{case_id}/members/{member_id}/accept", headers={"Authorization": f"Bearer {member_token}"}
    )

    response = await client.delete(f"/documents/{document_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 403
