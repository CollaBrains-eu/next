from unittest.mock import patch

from api.ldap_auth import LdapIdentity

_BUILT_IN_TOOLS = {"search", "summarize_document", "draft_legal_document", "extract_tasks", "extract_entities"}


async def _login(client) -> str:
    identity = LdapIdentity(
        username="toolsuser", display_name="Tools User", email="toolsuser@collabrains.eu", is_admin=False
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": "toolsuser", "password": "whatever"})
    return response.json()["access_token"]


async def test_list_tools_includes_all_built_in_tools(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/tools", headers=headers)

    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()}
    # subset, not equality -- other tests in this run may register their own tools too
    assert _BUILT_IN_TOOLS <= names


async def test_list_tools_reports_permissions_and_schemas(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/tools", headers=headers)
    tools_by_name = {tool["name"]: tool for tool in response.json()}

    search_tool = tools_by_name["search"]
    assert search_tool["permissions"] == ["documents.read"]
    assert "query" in search_tool["input_schema"]
    assert "documents" in search_tool["output_schema"]


async def test_list_tools_rejects_missing_token(client):
    response = await client.get("/tools")
    assert response.status_code == 401
