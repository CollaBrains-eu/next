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
