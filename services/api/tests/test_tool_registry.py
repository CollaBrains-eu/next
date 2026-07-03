from uuid import uuid4

import pytest

from api.tool_registry import ToolDescriptor, dispatch, get_tool, list_tools, register_tool


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


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
