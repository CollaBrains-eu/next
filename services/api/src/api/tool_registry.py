"""Tool Registry (Phase 9a, ADR 0021; permission enforcement Phase 9c, ADR 0023).

A tool is a descriptor (name, description, permissions, input/output
schema) plus a handler, registered at import time. This module only
holds the registry itself -- see api/tools.py for what actually gets
registered.

`dispatch()` is an in-process API only; it is deliberately not exposed
as a raw HTTP endpoint (see ADR 0021/0022 for why MCP's exposure of it
is safe without that). Permission enforcement (ADR 0023) lives here,
inside dispatch() itself, so no caller can forget to check: it's the
one chokepoint every tool call already goes through.
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
