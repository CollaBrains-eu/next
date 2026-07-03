"""Tool Registry (Phase 9a, ADR 0021).

A tool is a descriptor (name, description, permissions, input/output
schema) plus a handler, registered at import time. This module only
holds the registry itself -- see api/tools.py for what actually gets
registered.

Permissions are recorded on each descriptor but not enforced here --
that's Phase 9c's scope (see ADR 0021). `dispatch()` is an in-process
API only; it is deliberately not exposed as a raw HTTP endpoint before
permission enforcement exists.
"""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    description: str
    permissions: list[str]
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    handler: Callable[..., Awaitable[Any]]


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
    return await tool.handler(**kwargs)
