"""MCP Platform: expose the tool registry over the Model Context Protocol
(Phase 9b, ADR 0022).

Implements MCP's Streamable HTTP transport in its simplest, non-streaming
form: one JSON-RPC 2.0 request in, one JSON-RPC 2.0 response out. See
api/mcp_router.py for the actual HTTP endpoint; this module is the
protocol logic, testable without a running app.
"""
import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.tool_registry import ToolDescriptor, ToolPermissionError, dispatch, list_tools

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "collabrains-mcp"
SERVER_VERSION = "0.1.0"

METHOD_NOT_FOUND = -32601

# Never let a caller override these via `arguments` -- user_id must always
# come from the authenticated session, db from the request's own session.
_RESERVED_ARGUMENT_NAMES = {"db", "user_id"}


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


def _tool_to_mcp_schema(tool: ToolDescriptor) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": _input_schema_to_json_schema(tool.input_schema),
    }


def handle_initialize(params: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    }


def handle_tools_list(params: dict[str, Any] | None) -> dict[str, Any]:
    return {"tools": [_tool_to_mcp_schema(tool) for tool in list_tools()]}


async def handle_tools_call(params: dict[str, Any], *, db: AsyncSession, user_id: UUID) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments") or {}

    if not isinstance(name, str):
        return {"content": [{"type": "text", "text": "missing required param: name"}], "isError": True}

    reserved_used = _RESERVED_ARGUMENT_NAMES & arguments.keys()
    if reserved_used:
        return {
            "content": [
                {"type": "text", "text": f"arguments may not include: {', '.join(sorted(reserved_used))}"}
            ],
            "isError": True,
        }

    try:
        result = await dispatch(name, db=db, user_id=user_id, **arguments)
    except (KeyError, ValueError, ToolPermissionError) as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}

    return {"content": [{"type": "text", "text": json.dumps(result)}], "isError": False}


async def handle_request(request: dict[str, Any], *, db: AsyncSession, user_id: UUID) -> dict[str, Any]:
    """Dispatch one JSON-RPC 2.0 request to the appropriate MCP method handler."""
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    if method == "initialize":
        result = handle_initialize(params)
    elif method == "tools/list":
        result = handle_tools_list(params)
    elif method == "tools/call":
        result = await handle_tools_call(params, db=db, user_id=user_id)
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": METHOD_NOT_FOUND, "message": f"method not found: {method!r}"},
        }

    return {"jsonrpc": "2.0", "id": request_id, "result": result}
