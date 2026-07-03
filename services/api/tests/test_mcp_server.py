from unittest.mock import patch
from uuid import uuid4

from api.mcp_server import (
    _field_to_json_schema,
    _input_schema_to_json_schema,
    handle_initialize,
    handle_request,
    handle_tools_call,
    handle_tools_list,
)
from api.db import async_session
from api.models import User
from api.search_service import SearchHit
from api.tool_registry import ToolDescriptor, get_tool, register_tool


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str, *, role: str = "member") -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role=role)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


def test_field_to_json_schema_maps_real_tool_field_types():
    assert _field_to_json_schema("string") == {"type": "string"}
    assert _field_to_json_schema("string UUID") == {"type": "string"}
    assert _field_to_json_schema("integer (optional, default 10)") == {"type": "integer"}
    assert _field_to_json_schema("boolean (optional, regenerate cached summary)") == {"type": "boolean"}
    assert _field_to_json_schema("array of string UUIDs (optional, restricts search scope)") == {
        "type": "array",
        "items": {"type": "string"},
    }


def test_field_to_json_schema_defaults_to_string_for_unrecognized_prose():
    assert _field_to_json_schema("some made-up type") == {"type": "string"}


def test_input_schema_to_json_schema_marks_optional_fields_correctly():
    schema = _input_schema_to_json_schema({
        "document_id": "string UUID",
        "force": "boolean (optional, regenerate cached summary)",
    })
    assert schema["type"] == "object"
    assert schema["properties"]["document_id"] == {"type": "string"}
    assert schema["properties"]["force"] == {"type": "boolean"}
    assert schema["required"] == ["document_id"]


def test_handle_initialize_reports_tools_capability():
    result = handle_initialize(None)
    assert result["capabilities"] == {"tools": {}}
    assert "protocolVersion" in result
    assert result["serverInfo"]["name"]


def test_handle_tools_list_includes_all_built_in_tools_with_json_schema():
    result = handle_tools_list(None)
    tools_by_name = {tool["name"]: tool for tool in result["tools"]}

    for name in ("search", "summarize_document", "draft_legal_document", "extract_tasks", "extract_entities"):
        assert name in tools_by_name
        assert tools_by_name[name]["inputSchema"]["type"] == "object"

    search_schema = tools_by_name["search"]["inputSchema"]
    assert search_schema["properties"]["query"] == {"type": "string"}
    assert "query" in search_schema["required"]
    assert "limit" not in search_schema["required"]


async def test_handle_tools_call_dispatches_a_real_tool_end_to_end():
    user = await _create_user(_unique("mcpserveruser"))

    class _FakeChunk:
        def __init__(self):
            self.id = uuid4()
            self.document_id = uuid4()
            self.content = "hello from mcp"

    fake_hit = SearchHit(chunk=_FakeChunk(), score=0.5)

    async with async_session() as db:
        with patch("api.tools.hybrid_search", return_value=[fake_hit]):
            result = await handle_tools_call(
                {"name": "search", "arguments": {"query": "hello"}}, db=db, user_id=user.id,
            )

    assert result["isError"] is False
    assert "hello from mcp" in result["content"][0]["text"]


async def test_handle_tools_call_reports_permission_denial_as_error_not_exception():
    user = await _create_user(_unique("mcpserveruser"), role="service")

    async with async_session() as db:
        result = await handle_tools_call(
            {"name": "search", "arguments": {"query": "hello"}}, db=db, user_id=user.id,
        )

    assert result["isError"] is True


async def test_handle_tools_call_reports_unknown_tool_as_error_not_exception():
    result = await handle_tools_call({"name": _unique("nope")}, db=None, user_id=uuid4())
    assert result["isError"] is True


async def test_handle_tools_call_rejects_client_supplied_user_id():
    name = _unique("echo")

    async def handler(*, user_id, value):
        return {"value": value}

    register_tool(ToolDescriptor(
        name=name, description="d", permissions=[], input_schema={}, output_schema={}, handler=handler,
    ))

    result = await handle_tools_call(
        {"name": name, "arguments": {"user_id": str(uuid4()), "value": "x"}}, db=None, user_id=uuid4(),
    )

    assert result["isError"] is True
    assert "user_id" in result["content"][0]["text"]


async def test_handle_tools_call_rejects_missing_name():
    result = await handle_tools_call({}, db=None, user_id=uuid4())
    assert result["isError"] is True


async def test_handle_request_returns_method_not_found_for_unsupported_method():
    response = await handle_request({"jsonrpc": "2.0", "id": 1, "method": "resources/list"}, db=None, user_id=uuid4())
    assert response["error"]["code"] == -32601
    assert response["id"] == 1


async def test_handle_request_routes_initialize():
    response = await handle_request({"jsonrpc": "2.0", "id": 2, "method": "initialize"}, db=None, user_id=uuid4())
    assert response["result"]["serverInfo"]["name"]
    assert response["id"] == 2


async def test_handle_request_routes_tools_list():
    response = await handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, db=None, user_id=uuid4())
    assert "tools" in response["result"]


def test_register_tool_used_in_this_file_is_reachable_via_get_tool():
    # sanity check that the temp-tool pattern above actually registers -- guards
    # against a silently-broken register_tool import in future refactors
    name = _unique("sanity")

    async def handler(**kwargs):
        return {}

    register_tool(ToolDescriptor(
        name=name, description="d", permissions=[], input_schema={}, output_schema={}, handler=handler,
    ))
    assert get_tool(name) is not None
