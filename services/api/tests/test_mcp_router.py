from unittest.mock import patch
from uuid import uuid4

from api.ldap_auth import LdapIdentity
from api.search_service import SearchHit


async def _login(client) -> str:
    identity = LdapIdentity(
        username="mcpuser", display_name="MCP User", email="mcpuser@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "mcpuser", "password": "whatever"})
    return response.json()["access_token"]


async def test_mcp_initialize(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["capabilities"] == {"tools": {}}
    assert body["id"] == 1


async def test_mcp_tools_list_includes_built_in_tools(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )

    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert "search" in names


async def test_mcp_tools_call_invokes_the_authenticated_users_own_id(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    class _FakeChunk:
        def __init__(self):
            self.id = uuid4()
            self.document_id = uuid4()
            self.content = "mcp router result"

    fake_hit = SearchHit(chunk=_FakeChunk(), score=0.5)

    with patch("api.tools.hybrid_search", return_value=[fake_hit]):
        response = await client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": "hello"}},
            },
        )

    body = response.json()
    assert body["result"]["isError"] is False
    assert "mcp router result" in body["result"]["content"][0]["text"]


async def test_mcp_unknown_method_returns_json_rpc_error(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 4, "method": "prompts/list"},
    )

    assert response.json()["error"]["code"] == -32601


async def test_mcp_rejects_missing_token(client):
    response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 5, "method": "initialize"})
    assert response.status_code == 401
