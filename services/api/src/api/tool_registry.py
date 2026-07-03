"""Tool Registry (Phase 9a, ADR 0021; permission enforcement Phase 9c, ADR
0023; JSON-Schema translation + Ollama tool export Phase 9d, ADR 0024).

A tool is a descriptor (name, description, permissions, input/output
schema) plus a handler, registered at import time. This module only
holds the registry itself -- see api/tools.py for what actually gets
registered.

`dispatch()` is an in-process API only; it is deliberately not exposed
as a raw HTTP endpoint (see ADR 0021/0022 for why MCP's exposure of it
is safe without that). Permission enforcement (ADR 0023) lives here,
inside dispatch() itself, so no caller can forget to check: it's the
one chokepoint every tool call already goes through.

The JSON-Schema translator (_field_to_json_schema/
_input_schema_to_json_schema) lives here rather than in api/mcp_server.py
(where it was first written, ADR 0022) so both MCP's `inputSchema` and
Ollama's `parameters` -- the same JSON Schema shape, two different
wrapper formats -- can share it without api/mcp_server.py and this
module importing each other in a circle.
"""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from api.models import User
from api.permissions import has_permission


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    description: str
    permissions: list[str]
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    handler: Callable[..., Awaitable[Any]]


class ToolPermissionError(Exception):
    """Raised when the calling user's role lacks a tool's required permissions."""


_REGISTRY: dict[str, ToolDescriptor] = {}


def register_tool(descriptor: ToolDescriptor) -> None:
    if descriptor.name in _REGISTRY:
        raise ValueError(f"tool already registered: {descriptor.name!r}")
    _REGISTRY[descriptor.name] = descriptor


def get_tool(name: str) -> ToolDescriptor | None:
    return _REGISTRY.get(name)


def list_tools() -> list[ToolDescriptor]:
    return sorted(_REGISTRY.values(), key=lambda tool: tool.name)


async def dispatch(name: str, **kwargs: Any) -> Any:
    tool = get_tool(name)
    if tool is None:
        raise KeyError(f"unknown tool: {name!r}")

    if tool.permissions:
        db = kwargs.get("db")
        user_id = kwargs.get("user_id")
        if db is None or user_id is None:
            raise ToolPermissionError(
                f"tool {name!r} requires permissions {tool.permissions} but no db/user_id was provided"
            )
        user = await db.get(User, user_id)
        if user is None or not has_permission(user.role, tool.permissions):
            role = user.role if user is not None else None
            raise ToolPermissionError(
                f"role {role!r} lacks required permissions for tool {name!r}: {tool.permissions}"
            )

    return await tool.handler(**kwargs)


def _field_to_json_schema(prose: str) -> dict[str, Any]:
    """Best-effort translation of a ToolDescriptor prose type into JSON Schema.

    Deliberately narrow: maps the first word to string/integer/boolean/array,
    defaulting to string for anything unrecognized. See ADR 0022 for why this
    exists instead of changing ToolDescriptor.input_schema's format.
    """
    first_word = prose.strip().split()[0].lower() if prose.strip() else "string"
    json_type = first_word if first_word in {"string", "integer", "boolean", "array"} else "string"
    schema: dict[str, Any] = {"type": json_type}
    if json_type == "array":
        schema["items"] = {"type": "string"}
    return schema


def _input_schema_to_json_schema(input_schema: dict[str, str]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for field_name, prose in input_schema.items():
        properties[field_name] = _field_to_json_schema(prose)
        if "(optional" not in prose:
            required.append(field_name)
    return {"type": "object", "properties": properties, "required": required}


def to_ollama_tools() -> list[dict[str, Any]]:
    """Registered tools in Ollama/OpenAI-style function-calling schema.

    For api.ai_gateway.chat_completion_with_tools (Phase 9d, ADR 0024).
    Lists every registered tool regardless of any particular user's role --
    scoping which tools to offer a given user is a caller concern (see ADR
    0024), not something this function does.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": _input_schema_to_json_schema(tool.input_schema),
            },
        }
        for tool in list_tools()
    ]
