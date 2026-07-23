from unittest.mock import patch
from uuid import UUID

from api.ldap_auth import LdapIdentity

FAKE_EMBEDDING = [0.1] * 768


async def _login(client, username: str = "entityuser") -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _upload_ready_document(client, headers, text: str) -> str:
    # All five auto_extract_*_on_ready settings must be disabled here, not just tasks/
    # entities -- vehicles/classification/facts each fire a real chat_completion call on
    # EMBEDDINGS_CREATED too (documents.py), and on this deployment's genuinely slow,
    # semaphore-serialized Ollama, leaving any of them enabled turns every upload in this
    # file into a multi-minute real LLM call instead of the fast, fully-mocked test this
    # helper is meant to provide.
    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value=text),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_classify_on_ready", False),
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("case.txt", text.encode(), "text/plain")}
        )
    return upload.json()["id"]


# Extraction fixtures use "organization" (an AUTO_EXTRACTED_ENTITY_TYPES member) even for
# person-shaped names -- these tests exercise dedup/status-transition mechanics that are
# type-agnostic, and only "organization"/"address" are auto-created (see entity_agent.py).
FAKE_EXTRACTION = (
    '{"entities": [{"name": "Sarah Miller", "type": "organization"}, {"name": "Acme Corp", "type": "organization"}], '
    '"relationships": [{"source": "Sarah Miller", "target": "Acme Corp", "type": "represents"}]}'
)


async def test_extract_entities_persists_entities_mentions_and_relationships(client):
    token = await _login(client, "entityuser1")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Sarah Miller represents Acme Corp.")

    with patch("api.entity_agent.chat_completion", return_value=FAKE_EXTRACTION) as mock_completion:
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert {e["name"] for e in entities} == {"Sarah Miller", "Acme Corp"}
    assert {e["entity_type"] for e in entities} == {"organization"}

    from api.entity_agent import EXTRACTION_SCHEMA

    assert mock_completion.call_args.kwargs["schema"] == EXTRACTION_SCHEMA


async def test_extract_entities_deduplicates_by_case_insensitive_name_and_type(client):
    token = await _login(client, "entityuser2")
    headers = {"Authorization": f"Bearer {token}"}
    doc_a = await _upload_ready_document(client, headers, "Wanda Cole represents Beacon Inc.")
    doc_b = await _upload_ready_document(client, headers, "wanda cole filed another motion.")

    fake_first = (
        '{"entities": [{"name": "Wanda Cole", "type": "organization"}, {"name": "Beacon Inc", "type": "organization"}], '
        '"relationships": []}'
    )
    fake_second = '{"entities": [{"name": "wanda cole", "type": "organization"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake_first):
        await client.post(f"/documents/{doc_a}/extract-entities", headers=headers)
    with patch("api.entity_agent.chat_completion", return_value=fake_second):
        await client.post(f"/documents/{doc_b}/extract-entities", headers=headers)

    # status="all": newly-extracted entities start pending_review, and this
    # test is about dedup, not the review-status filter GET /entities
    # defaults to (added later, in a3cec2f, without updating this test).
    listing = await client.get("/entities", headers=headers, params={"q": "wanda", "status": "all"})
    names = [e["name"] for e in listing.json()]
    assert names == ["Wanda Cole"]  # one row, not two, despite different casing across documents


async def test_extract_entities_skips_relationships_referencing_unknown_entities(client):
    token = await _login(client, "entityuser3")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Some text.")

    fake = (
        '{"entities": [{"name": "Bob Anders", "type": "organization"}], '
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


async def test_extract_entities_auto_creates_person_and_location(client):
    """Reversed 2026-07-23: person/location were pulled from auto-extraction on
    2026-07-09 for being "the dominant source of low-quality noise", before any
    code-level guardrail existed. Now that _looks_like_garbage_address (and its
    generalization here) exists, both are auto-created like organization/address
    always were. See docs/superpowers/plans/2026-07-23-reliable-entity-extraction-maps.md."""
    token = await _login(client, "entityuser16")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "A person visits a place.")

    fake = (
        '{"entities": [{"name": "Random Person", "type": "person"}, '
        '{"name": "Random Place", "type": "location"}], "relationships": []}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert {e["name"] for e in entities} == {"Random Person", "Random Place"}
    assert {e["entity_type"] for e in entities} == {"person", "location"}

    listing = await client.get("/entities", headers=headers, params={"q": "Random", "status": "all"})
    assert len(listing.json()) == 2


async def test_entity_graph_returns_one_hop_neighbors_and_edges(client):
    token = await _login(client, "entityuser5")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Priya Patel represents Zenith Ltd.")

    fake_extraction = (
        '{"entities": [{"name": "Priya Patel", "type": "organization"}, {"name": "Zenith Ltd", "type": "organization"}], '
        '"relationships": [{"source": "Priya Patel", "target": "Zenith Ltd", "type": "represents"}]}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake_extraction):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    entities_by_name = {e["name"]: e["id"] for e in extracted.json()}

    # The graph only shows confirmed neighbors/edges (Phase 21) -- approve
    # both extracted entities before checking the graph.
    await client.post(f"/entities/{entities_by_name['Priya Patel']}/approve", headers=headers)
    await client.post(f"/entities/{entities_by_name['Zenith Ltd']}/approve", headers=headers)

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
        '{"entities": [{"name": "Nadia Petrov", "type": "organization"}], "relationships": []}'
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

    fake = '{"entities": [{"name": "Omar Reyes", "type": "organization"}], "relationships": []}'
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

    fake = '{"entities": [{"name": "Priya Nair", "type": "organization"}], "relationships": []}'
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

    fake = '{"entities": [{"name": "088 227 77 00", "type": "organization"}], "relationships": []}'
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

    fake = '{"entities": [{"name": "Karl Zimmer", "type": "organization"}], "relationships": []}'
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
    fake = '{"entities": [{"name": "Liu Wei", "type": "organization"}], "relationships": []}'
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
    fake = '{"entities": [{"name": "23.10.2025", "type": "organization"}], "relationships": []}'
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
    fake = '{"entities": [{"name": "Rosa Diaz", "type": "organization"}], "relationships": []}'
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
        '{"entities": [{"name": "Tom Baker", "type": "organization"}, {"name": "14 februari 2024", "type": "organization"}], '
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


async def test_entity_graph_excludes_non_confirmed_neighbors(client):
    token = await _login(client, "entityuser15")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Elena Kravitz represents Vantage Group.")

    fake = (
        '{"entities": [{"name": "Elena Kravitz", "type": "organization"}, {"name": "Vantage Group", "type": "organization"}], '
        '"relationships": [{"source": "Elena Kravitz", "target": "Vantage Group", "type": "represents"}]}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)
    ids_by_name = {e["name"]: e["id"] for e in extracted.json()}
    center_id = ids_by_name["Elena Kravitz"]

    # Center confirmed, neighbor still pending_review (default post-extraction state).
    await client.post(f"/entities/{center_id}/approve", headers=headers)

    graph = await client.get(f"/entities/{center_id}/graph", headers=headers)
    assert graph.json()["nodes"] == []  # Vantage Group is still pending, so it's excluded
    assert graph.json()["edges"] == []  # the edge to a non-confirmed neighbor is excluded too


async def test_create_entity_manually_starts_confirmed(client):
    token = await _login(client, "entityuser17")
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post("/entities", headers=headers, json={"name": "Jane Cooper", "entity_type": "person"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Jane Cooper"
    assert body["entity_type"] == "person"
    assert body["status"] == "confirmed"

    listing = await client.get("/entities", headers=headers, params={"q": "Jane Cooper"})
    assert len(listing.json()) == 1  # visible in the default confirmed-only listing


async def test_create_entity_rejects_empty_name(client):
    token = await _login(client, "entityuser18")
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post("/entities", headers=headers, json={"name": "   ", "entity_type": "person"})
    assert response.status_code == 400


async def test_create_entity_rejects_invalid_type(client):
    token = await _login(client, "entityuser19")
    headers = {"Authorization": f"Bearer {token}"}

    vehicle_response = await client.post("/entities", headers=headers, json={"name": "Some Car", "entity_type": "vehicle"})
    assert vehicle_response.status_code == 400

    other_response = await client.post("/entities", headers=headers, json={"name": "Whatever", "entity_type": "other"})
    assert other_response.status_code == 400


async def test_create_entity_deduplicates_and_reconfirms_rejected(client):
    token = await _login(client, "entityuser20")
    headers = {"Authorization": f"Bearer {token}"}
    first = await client.post("/entities", headers=headers, json={"name": "Dedup Person", "entity_type": "person"})
    entity_id = first.json()["id"]

    same = await client.post("/entities", headers=headers, json={"name": "dedup person", "entity_type": "person"})
    assert same.status_code == 201
    assert same.json()["id"] == entity_id  # case-insensitive dedup, not a duplicate row

    from api.models import Entity
    from api.db import async_session
    async with async_session() as db:
        entity = await db.get(Entity, UUID(entity_id))
        entity.status = "rejected"
        await db.commit()

    recreated = await client.post("/entities", headers=headers, json={"name": "Dedup Person", "entity_type": "person"})
    assert recreated.status_code == 201
    assert recreated.json()["id"] == entity_id
    assert recreated.json()["status"] == "confirmed"  # manual creation reconfirms, doesn't respect the prior rejection


async def test_create_entity_rejects_missing_token(client):
    response = await client.post("/entities", json={"name": "Nobody", "entity_type": "person"})
    assert response.status_code == 401


async def test_pending_review_count_reflects_newly_extracted_entities(client):
    token = await _login(client, "entityuser21")
    headers = {"Authorization": f"Bearer {token}"}
    before = (await client.get("/entities/pending-review-count", headers=headers)).json()["count"]

    doc_a = await _upload_ready_document(client, headers, "Globex Corp appears here.")
    doc_b = await _upload_ready_document(client, headers, "Initech Inc appears here.")
    fake_a = '{"entities": [{"name": "Globex Corp", "type": "organization"}], "relationships": []}'
    fake_b = '{"entities": [{"name": "Initech Inc", "type": "organization"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake_a):
        await client.post(f"/documents/{doc_a}/extract-entities", headers=headers)
    with patch("api.entity_agent.chat_completion", return_value=fake_b):
        await client.post(f"/documents/{doc_b}/extract-entities", headers=headers)

    after = (await client.get("/entities/pending-review-count", headers=headers)).json()["count"]
    assert after == before + 2  # both newly extracted, still pending_review


async def test_pending_review_count_rejects_missing_token(client):
    response = await client.get("/entities/pending-review-count")
    assert response.status_code == 401


async def test_entities_list_excludes_another_owners_entities(client):
    owner_token = await _login(client, "entityuser22")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    create = await client.post(
        "/entities", headers=owner_headers, json={"name": "Owner Only Person", "entity_type": "person"}
    )
    assert create.status_code == 201

    other_token = await _login(client, "entityuser23")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    listing = await client.get(
        "/entities", headers=other_headers, params={"q": "Owner Only Person", "status": "all"}
    )
    assert listing.json() == []  # another account's entity must not leak into this list


async def test_pending_review_count_excludes_another_owners_pending_entities(client):
    owner_token = await _login(client, "entityuser24")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    document_id = await _upload_ready_document(client, owner_headers, "Umbrella Corp appears here.")
    fake = '{"entities": [{"name": "Umbrella Corp", "type": "organization"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        await client.post(f"/documents/{document_id}/extract-entities", headers=owner_headers)

    other_token = await _login(client, "entityuser25")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    before = (await client.get("/entities/pending-review-count", headers=other_headers)).json()["count"]
    # the owner's own count includes it, but a different account's count must not
    owner_count = (await client.get("/entities/pending-review-count", headers=owner_headers)).json()["count"]
    assert owner_count >= 1
    assert before == 0  # entityuser25 is a fresh account with nothing pending of its own


async def test_approve_entity_rejects_non_owner(client):
    owner_token = await _login(client, "entityuser26")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    document_id = await _upload_ready_document(client, owner_headers, "Wayne Enterprises appears here.")
    fake = '{"entities": [{"name": "Wayne Enterprises", "type": "organization"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=owner_headers)
    entity_id = extracted.json()[0]["id"]

    intruder_token = await _login(client, "entityuser27")
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}
    response = await client.post(f"/entities/{entity_id}/approve", headers=intruder_headers)
    assert response.status_code == 403


async def test_entity_graph_rejects_non_owner(client):
    owner_token = await _login(client, "entityuser28")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    document_id = await _upload_ready_document(client, owner_headers, "Stark Industries appears here.")
    fake = '{"entities": [{"name": "Stark Industries", "type": "organization"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=owner_headers)
    entity_id = extracted.json()[0]["id"]

    intruder_token = await _login(client, "entityuser29")
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}
    response = await client.get(f"/entities/{entity_id}/graph", headers=intruder_headers)
    assert response.status_code == 403


async def test_extract_entities_rejects_extracting_from_another_owners_document(client):
    owner_token = await _login(client, "entityuser30")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    document_id = await _upload_ready_document(client, owner_headers, "Some private text.")

    intruder_token = await _login(client, "entityuser31")
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}
    response = await client.post(f"/documents/{document_id}/extract-entities", headers=intruder_headers)
    assert response.status_code == 403


async def test_same_named_entity_is_independent_across_two_owners(client):
    token_a = await _login(client, "entityuser32")
    token_b = await _login(client, "entityuser33")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    create_a = await client.post("/entities", headers=headers_a, json={"name": "Shared Name Inc", "entity_type": "organization"})
    create_b = await client.post("/entities", headers=headers_b, json={"name": "Shared Name Inc", "entity_type": "organization"})

    assert create_a.status_code == 201
    assert create_b.status_code == 201
    assert create_a.json()["id"] != create_b.json()["id"]  # same name+type, different accounts -- not deduped together


async def test_extraction_rejects_email_as_address(client):
    token = await _login(client, "entityuser-emailreject")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "contact us")
    fake = (
        '{"entities": [{"name": "user@example.com", "type": "address"}], "relationships": []}'
    )

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_extraction_rejects_url_as_address(client):
    token = await _login(client, "entityuser-urlreject")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "visit us")
    fake = '{"entities": [{"name": "www.example.com", "type": "address"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_extraction_rejects_person_salutation_as_address(client):
    token = await _login(client, "entityuser-salutationreject")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "letter")
    fake = '{"entities": [{"name": "t.a.v. mevrouw A. Thole", "type": "address"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_extraction_rejects_phone_number_as_address(client):
    """Live bug found 2026-07-23 verifying against a real document: the LLM extracted
    a phone number both as a person's "phone" field (correct) AND as a separate
    entity_type="address" item with the phone number as its name -- the existing
    garbage-address guardrail predates phone numbers being a concept in this pipeline
    and didn't reject them."""
    token = await _login(client, "entityuser-phonereject")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "form")
    fake = '{"entities": [{"name": "+31 6 27996943", "type": "address"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_extraction_fills_structured_fields_when_llm_leaves_them_null(client):
    """The live bug this fixes: the LLM's schema-constrained output is often
    {"name": "Achterweg 15", "type": "address", "street": null, ...} --
    address_parser must fill the gaps from the name string."""
    token = await _login(client, "entityuser-fillfields")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "letter")
    fake = (
        '{"entities": [{"name": "Achterweg 15", "type": "address", "street": null, '
        '"house_number": null, "postal_code": null, "city": null, "country": null}], '
        '"relationships": []}'
    )

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert len(entities) == 1

    from api.db import async_session
    from api.models import AddressDetail
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(AddressDetail).where(AddressDetail.entity_id == entities[0]["id"]))
        detail = result.scalar_one()
    assert detail.street == "Achterweg"
    assert detail.house_number == "15"


async def test_person_entities_are_now_auto_extracted(client):
    token = await _login(client, "entityuser-personauto")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Letter from Jan de Vries.")
    fake = '{"entities": [{"name": "Jan de Vries", "type": "person"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "person"


async def test_location_entities_are_now_auto_extracted(client):
    token = await _login(client, "entityuser-locationauto")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Meeting held in Amsterdam.")
    fake = '{"entities": [{"name": "Amsterdam", "type": "location"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "location"


async def test_extraction_creates_contact_detail_for_organization(client):
    """Karl Zimmer / Umbrella Corp letterhead case: phone + PO box + visiting
    address attach to the organization entity, with PO box/visiting address
    becoming their own deduped address entities via the existing machinery."""
    token = await _login(client, "entityuser-contact1")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Umbrella Corp letterhead")
    fake = (
        '{"entities": [{"name": "Umbrella Corp", "type": "organization", '
        '"phone": "010-1234567", "po_box": "Postbus 99, 1000 AB Amsterdam", '
        '"visiting_address": "Hoofdstraat 1, 1011 AB Amsterdam"}], "relationships": []}'
    )

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert len(entities) == 1
    contact = entities[0]["contact"]
    assert contact["phone"] == "010-1234567"
    assert contact["po_box_address"] is not None
    assert contact["po_box_address"]["city"] == "Amsterdam"
    assert contact["visiting_address"] is not None
    assert contact["visiting_address"]["street"] == "Hoofdstraat"


async def test_contact_detail_gap_fills_across_documents_not_overwrite(client):
    token = await _login(client, "entityuser-contact2")
    headers = {"Authorization": f"Bearer {token}"}
    doc1 = await _upload_ready_document(client, headers, "First letter")
    fake1 = '{"entities": [{"name": "Acme BV", "type": "organization", "phone": "010-1234567"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake1):
        r1 = await client.post(f"/documents/{doc1}/extract-entities", headers=headers)
    assert r1.json()[0]["contact"]["phone"] == "010-1234567"

    doc2 = await _upload_ready_document(client, headers, "Second letter")
    fake2 = '{"entities": [{"name": "Acme BV", "type": "organization", "phone": "999-9999999"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake2):
        r2 = await client.post(f"/documents/{doc2}/extract-entities", headers=headers)

    assert r2.json()[0]["contact"]["phone"] == "010-1234567"


async def test_extraction_rejects_garbage_phone_and_title(client):
    token = await _login(client, "entityuser-contact3")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Third letter")
    fake = (
        '{"entities": [{"name": "Karl Zimmer", "type": "person", "phone": "info@acme.com"}, '
        '{"name": "Acme BV", "type": "organization"}], '
        '"relationships": [{"source": "Karl Zimmer", "target": "Acme BV", "type": "employee_of", '
        '"title": "https://acme.com"}]}'
    )

    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    entities_by_name = {e["name"]: e for e in extracted.json()}
    assert entities_by_name["Karl Zimmer"]["contact"] is None

    person_id = entities_by_name["Karl Zimmer"]["id"]
    org_id = entities_by_name["Acme BV"]["id"]
    await client.post(f"/entities/{person_id}/approve", headers=headers)
    await client.post(f"/entities/{org_id}/approve", headers=headers)
    graph = await client.get(f"/entities/{person_id}/graph", headers=headers)
    assert graph.json()["edges"][0]["title"] is None


async def test_relationship_title_is_extracted_and_serialized_in_graph(client):
    token = await _login(client, "entityuser-title1")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Karl Zimmer, Directeur bij Umbrella Corp.")
    fake = (
        '{"entities": [{"name": "Karl Zimmer", "type": "person"}, {"name": "Umbrella Corp", "type": "organization"}], '
        '"relationships": [{"source": "Karl Zimmer", "target": "Umbrella Corp", "type": "employee_of", "title": "Directeur"}]}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    entities_by_name = {e["name"]: e["id"] for e in extracted.json()}
    await client.post(f"/entities/{entities_by_name['Karl Zimmer']}/approve", headers=headers)
    await client.post(f"/entities/{entities_by_name['Umbrella Corp']}/approve", headers=headers)

    graph = await client.get(f"/entities/{entities_by_name['Karl Zimmer']}/graph", headers=headers)
    edge = graph.json()["edges"][0]
    assert edge["title"] == "Directeur"
