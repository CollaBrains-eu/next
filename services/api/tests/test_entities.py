from unittest.mock import patch

from api.ldap_auth import LdapIdentity

FAKE_EMBEDDING = [0.1] * 768


async def _login(client, username: str = "entityuser") -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _upload_ready_document(client, headers, text: str) -> str:
    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value=text),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("case.txt", text.encode(), "text/plain")}
        )
    return upload.json()["id"]


FAKE_EXTRACTION = (
    '{"entities": [{"name": "Sarah Miller", "type": "person"}, {"name": "Acme Corp", "type": "organization"}], '
    '"relationships": [{"source": "Sarah Miller", "target": "Acme Corp", "type": "represents"}]}'
)


async def test_extract_entities_persists_entities_mentions_and_relationships(client):
    token = await _login(client, "entityuser1")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Sarah Miller represents Acme Corp.")

    with patch("api.entity_agent.chat_completion", return_value=FAKE_EXTRACTION):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert {e["name"] for e in entities} == {"Sarah Miller", "Acme Corp"}
    assert {e["entity_type"] for e in entities} == {"person", "organization"}


async def test_extract_entities_deduplicates_by_case_insensitive_name_and_type(client):
    token = await _login(client, "entityuser2")
    headers = {"Authorization": f"Bearer {token}"}
    doc_a = await _upload_ready_document(client, headers, "Wanda Cole represents Beacon Inc.")
    doc_b = await _upload_ready_document(client, headers, "wanda cole filed another motion.")

    fake_first = (
        '{"entities": [{"name": "Wanda Cole", "type": "person"}, {"name": "Beacon Inc", "type": "organization"}], '
        '"relationships": []}'
    )
    fake_second = '{"entities": [{"name": "wanda cole", "type": "person"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake_first):
        await client.post(f"/documents/{doc_a}/extract-entities", headers=headers)
    with patch("api.entity_agent.chat_completion", return_value=fake_second):
        await client.post(f"/documents/{doc_b}/extract-entities", headers=headers)

    listing = await client.get("/entities", headers=headers, params={"q": "wanda"})
    names = [e["name"] for e in listing.json()]
    assert names == ["Wanda Cole"]  # one row, not two, despite different casing across documents


async def test_extract_entities_skips_relationships_referencing_unknown_entities(client):
    token = await _login(client, "entityuser3")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    fake = (
        '{"entities": [{"name": "Bob Anders", "type": "person"}], '
        '"relationships": [{"source": "Bob Anders", "target": "Ghost Entity", "type": "knows"}]}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    entity_id = response.json()[0]["id"]
    graph = await client.get(f"/entities/{entity_id}/graph", headers=headers)
    assert graph.json()["edges"] == []


async def test_extract_entities_handles_unparseable_output_gracefully(client):
    token = await _login(client, "entityuser4")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    with patch("api.entity_agent.chat_completion", return_value="not json"):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_entity_graph_returns_one_hop_neighbors_and_edges(client):
    token = await _login(client, "entityuser5")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Priya Patel represents Zenith Ltd.")

    fake_extraction = (
        '{"entities": [{"name": "Priya Patel", "type": "person"}, {"name": "Zenith Ltd", "type": "organization"}], '
        '"relationships": [{"source": "Priya Patel", "target": "Zenith Ltd", "type": "represents"}]}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake_extraction):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    entities_by_name = {e["name"]: e["id"] for e in extracted.json()}

    graph = await client.get(f"/entities/{entities_by_name['Priya Patel']}/graph", headers=headers)
    body = graph.json()
    assert body["center"]["name"] == "Priya Patel"
    assert [n["name"] for n in body["nodes"]] == ["Zenith Ltd"]
    assert len(body["edges"]) == 1
    assert body["edges"][0]["relationship_type"] == "represents"


async def test_extract_entities_rejects_missing_token(client):
    response = await client.post("/documents/00000000-0000-0000-0000-000000000000/extract-entities")
    assert response.status_code == 401


async def test_list_entities_rejects_missing_token(client):
    response = await client.get("/entities")
    assert response.status_code == 401


async def test_new_entities_are_created_as_pending_review(client):
    token = await _login(client, "entityuser5")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Nadia Petrov works at Fenwick LLC.")

    fake = (
        '{"entities": [{"name": "Nadia Petrov", "type": "person"}], "relationships": []}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["status"] == "pending_review"


async def test_extraction_reuses_confirmed_entity_without_creating_pending_row(client):
    token = await _login(client, "entityuser6")
    headers = {"Authorization": f"Bearer {token}"}
    doc_a = await _upload_ready_document(client, headers, "Omar Reyes signed the lease.")
    doc_b = await _upload_ready_document(client, headers, "Omar Reyes called again today.")

    fake = '{"entities": [{"name": "Omar Reyes", "type": "person"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        first = await client.post(f"/documents/{doc_a}/extract-entities", headers=headers)
    entity_id = first.json()[0]["id"]

    # Manually confirm it, the way the approve endpoint will in Task 4.
    from api.models import Entity
    from api.db import async_session
    async with async_session() as db:
        entity = await db.get(Entity, entity_id)
        entity.status = "confirmed"
        await db.commit()

    with patch("api.entity_agent.chat_completion", return_value=fake):
        second = await client.post(f"/documents/{doc_b}/extract-entities", headers=headers)

    assert len(second.json()) == 1
    assert second.json()[0]["id"] == entity_id
    assert second.json()[0]["status"] == "confirmed"

    listing = await client.get("/entities", headers=headers, params={"q": "Omar", "status": "all"})
    assert len(listing.json()) == 1  # still exactly one row, not a duplicate pending one


async def test_extraction_attaches_new_mention_to_existing_pending_entity(client):
    token = await _login(client, "entityuser7")
    headers = {"Authorization": f"Bearer {token}"}
    doc_a = await _upload_ready_document(client, headers, "Priya Nair filed a claim.")
    doc_b = await _upload_ready_document(client, headers, "Priya Nair called the adjuster.")

    fake = '{"entities": [{"name": "Priya Nair", "type": "person"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        first = await client.post(f"/documents/{doc_a}/extract-entities", headers=headers)
    with patch("api.entity_agent.chat_completion", return_value=fake):
        second = await client.post(f"/documents/{doc_b}/extract-entities", headers=headers)

    assert first.json()[0]["id"] == second.json()[0]["id"]
    listing = await client.get("/entities", headers=headers, params={"q": "Priya Nair", "status": "all"})
    assert len(listing.json()) == 1  # one pending row shared by both mentions, not two


async def test_extraction_suppresses_rejected_entity(client):
    token = await _login(client, "entityuser8")
    headers = {"Authorization": f"Bearer {token}"}
    doc_a = await _upload_ready_document(client, headers, "088 227 77 00 is listed.")

    fake = '{"entities": [{"name": "088 227 77 00", "type": "other"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        first = await client.post(f"/documents/{doc_a}/extract-entities", headers=headers)
    entity_id = first.json()[0]["id"]

    from api.models import Entity
    from api.db import async_session
    async with async_session() as db:
        entity = await db.get(Entity, entity_id)
        entity.status = "rejected"
        await db.commit()

    doc_b = await _upload_ready_document(client, headers, "Call 088 227 77 00 for support.")
    with patch("api.entity_agent.chat_completion", return_value=fake):
        second = await client.post(f"/documents/{doc_b}/extract-entities", headers=headers)

    assert second.json() == []  # suppressed, not recreated
    listing = await client.get("/entities", headers=headers, params={"q": "088 227 77 00", "status": "all"})
    assert len(listing.json()) == 1  # still just the original rejected row


async def test_list_entities_defaults_to_confirmed_only(client):
    token = await _login(client, "entityuser9")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Karl Zimmer is a witness.")

    fake = '{"entities": [{"name": "Karl Zimmer", "type": "person"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    default_listing = await client.get("/entities", headers=headers, params={"q": "Karl Zimmer"})
    assert default_listing.json() == []  # pending_review entities are hidden by default

    pending_listing = await client.get("/entities", headers=headers, params={"q": "Karl Zimmer", "status": "pending_review"})
    assert len(pending_listing.json()) == 1

    all_listing = await client.get("/entities", headers=headers, params={"q": "Karl Zimmer", "status": "all"})
    assert len(all_listing.json()) == 1


async def test_approve_entity_transitions_pending_to_confirmed(client):
    token = await _login(client, "entityuser10")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Liu Wei is a party.")
    fake = '{"entities": [{"name": "Liu Wei", "type": "person"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)
    entity_id = extracted.json()[0]["id"]

    response = await client.post(f"/entities/{entity_id}/approve", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    listing = await client.get("/entities", headers=headers, params={"q": "Liu Wei"})
    assert len(listing.json()) == 1  # now visible in the default (confirmed-only) listing


async def test_reject_entity_transitions_pending_to_rejected(client):
    token = await _login(client, "entityuser11")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "23.10.2025 appears here.")
    fake = '{"entities": [{"name": "23.10.2025", "type": "other"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)
    entity_id = extracted.json()[0]["id"]

    response = await client.post(f"/entities/{entity_id}/reject", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


async def test_approve_nonexistent_entity_returns_404(client):
    token = await _login(client, "entityuser12")
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post("/entities/00000000-0000-0000-0000-000000000000/approve", headers=headers)
    assert response.status_code == 404


async def test_approve_already_confirmed_entity_returns_409(client):
    token = await _login(client, "entityuser13")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Second approve attempt.")
    fake = '{"entities": [{"name": "Rosa Diaz", "type": "person"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)
    entity_id = extracted.json()[0]["id"]

    await client.post(f"/entities/{entity_id}/approve", headers=headers)
    second = await client.post(f"/entities/{entity_id}/approve", headers=headers)
    assert second.status_code == 409


async def test_bulk_review_approves_and_rejects_in_one_request(client):
    token = await _login(client, "entityuser14")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Two entities appear.")
    fake = (
        '{"entities": [{"name": "Tom Baker", "type": "person"}, {"name": "14 februari 2024", "type": "other"}], '
        '"relationships": []}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)
    ids_by_name = {e["name"]: e["id"] for e in extracted.json()}

    response = await client.post(
        "/entities/bulk-review",
        headers=headers,
        json=[
            {"entity_id": ids_by_name["Tom Baker"], "action": "approve"},
            {"entity_id": ids_by_name["14 februari 2024"], "action": "reject"},
        ],
    )
    assert response.status_code == 200
    results = {r["id"]: r["status"] for r in response.json()}
    assert results[ids_by_name["Tom Baker"]] == "confirmed"
    assert results[ids_by_name["14 februari 2024"]] == "rejected"
