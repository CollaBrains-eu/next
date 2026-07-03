"""Tool discovery endpoint (Phase 9a, ADR 0021).

Read-only: lists registered tools' descriptors. Dispatch itself is an
in-process API only (api.tool_registry.dispatch) -- not exposed here,
since permission enforcement doesn't exist yet (Phase 9c).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.auth import get_current_user
from api.models import User
from api.tool_registry import list_tools

router = APIRouter(tags=["tools"])


class ToolOut(BaseModel):
    name: str
    description: str
    permissions: list[str]
    input_schema: dict[str, str]
    output_schema: dict[str, str]


@router.get("/tools", response_model=list[ToolOut])
async def list_tools_endpoint(current_user: User = Depends(get_current_user)) -> list[ToolOut]:
    return [
        ToolOut(
            name=tool.name,
            description=tool.description,
            permissions=tool.permissions,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
        )
        for tool in list_tools()
    ]
