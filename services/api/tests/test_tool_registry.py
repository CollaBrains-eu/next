from uuid import uuid4

import pytest

from api.db import async_session
from api.models import User
from api.tool_registry import (
    ToolDescriptor,
    ToolPermissionError,
    _field_to_json_schema,
    _input_schema_to_json_schema,
    dispatch,
    get_tool,
    list_tools,
    register_tool,
    to_ollama_tools,
)


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str, *, role: str = "member") -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role=role)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def test_register_and_get_tool():
    name = _unique("echo")

    async def handler(*, value):
        return {"value": value}

    register_tool(ToolDescriptor(
        name=name, description="echoes input", permissions=["demo.read"],
        input_schema={"value": "string"}, output_schema={"value": "string"}, handler=handler,
    ))

    tool = get_tool(name)
    assert tool is not None
    assert tool.description == "echoes input"
    assert tool.permissions == ["demo.read"]


async def test_get_tool_returns_none_for_unknown_name():
    assert get_tool(_unique("does-not-exist")) is None


async def test_register_tool_rejects_duplicate_name():
    name = _unique("dupe")

    async def handler(**kwargs):
        return {}

    descriptor = ToolDescriptor(
        name=name, description="d", permissions=[], input_schema={}, output_schema={}, handler=handler,
    )
    register_tool(descriptor)

    with pytest.raises(ValueError):
        register_tool(descriptor)


async def test_list_tools_includes_registered_tool_sorted_by_name():
    name = _unique("zzz-listed")

    async def handler(**kwargs):
        return {}

    register_tool(ToolDescriptor(
        name=name, description="d", permissions=[], input_schema={}, output_schema={}, handler=handler,
    ))

    names = [tool.name for tool in list_tools()]
    assert name in names
    assert names == sorted(names)


async def test_dispatch_calls_the_registered_handler():
    name = _unique("adder")

    async def handler(*, a, b):
        return {"sum": a + b}

    register_tool(ToolDescriptor(
        name=name, description="d", permissions=[], input_schema={}, output_schema={}, handler=handler,
    ))

    result = await dispatch(name, a=2, b=3)
    assert result == {"sum": 5}


async def test_dispatch_unknown_tool_raises_key_error():
    with pytest.raises(KeyError):
        await dispatch(_unique("does-not-exist"))


async def test_dispatch_allows_a_role_with_the_required_permission():
    name = _unique("gated")
    user = await _create_user(_unique("registryuser"), role="member")

    async def handler(*, db, user_id):
        return {"ok": True}

    register_tool(ToolDescriptor(
        name=name, description="d", permissions=["documents.read"],
        input_schema={}, output_schema={}, handler=handler,
    ))

    async with async_session() as db:
        result = await dispatch(name, db=db, user_id=user.id)

    assert result == {"ok": True}


async def test_dispatch_denies_a_role_without_the_required_permission():
    name = _unique("gated")
    user = await _create_user(_unique("registryuser"), role="service")

    async def handler(*, db, user_id):
        return {"ok": True}

    register_tool(ToolDescriptor(
        name=name, description="d", permissions=["documents.read"],
        input_schema={}, output_schema={}, handler=handler,
    ))

    async with async_session() as db:
        with pytest.raises(ToolPermissionError):
            await dispatch(name, db=db, user_id=user.id)


async def test_dispatch_denies_a_permission_requiring_tool_with_no_db_or_user_id():
    name = _unique("gated-no-context")

    async def handler(**kwargs):
        return {"ok": True}

    register_tool(ToolDescriptor(
        name=name, description="d", permissions=["documents.read"],
        input_schema={}, output_schema={}, handler=handler,
    ))

    with pytest.raises(ToolPermissionError):
        await dispatch(name)


async def test_dispatch_denies_an_unknown_user_id():
    name = _unique("gated-unknown-user")

    async def handler(**kwargs):
        return {"ok": True}

    register_tool(ToolDescriptor(
        name=name, description="d", permissions=["documents.read"],
        input_schema={}, output_schema={}, handler=handler,
    ))

    async with async_session() as db:
        with pytest.raises(ToolPermissionError):
            await dispatch(name, db=db, user_id=uuid4())


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


def test_to_ollama_tools_includes_all_built_in_tools_as_function_definitions():
    functions_by_name = {entry["function"]["name"]: entry for entry in to_ollama_tools()}

    for name in ("search", "summarize_document", "draft_legal_document", "extract_tasks", "extract_entities"):
        assert name in functions_by_name
        entry = functions_by_name[name]
        assert entry["type"] == "function"
        assert entry["function"]["parameters"]["type"] == "object"

    search_params = functions_by_name["search"]["function"]["parameters"]
    assert search_params["properties"]["query"] == {"type": "string"}
    assert "query" in search_params["required"]


def test_to_ollama_tools_includes_a_freshly_registered_tool():
    name = _unique("ollama-tool")

    async def handler(**kwargs):
        return {}

    register_tool(ToolDescriptor(
        name=name, description="a demo tool", permissions=[],
        input_schema={"value": "string"}, output_schema={}, handler=handler,
    ))

    functions_by_name = {entry["function"]["name"]: entry for entry in to_ollama_tools()}
    assert name in functions_by_name
    assert functions_by_name[name]["function"]["description"] == "a demo tool"
