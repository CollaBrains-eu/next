"""POST /mcp: MCP Streamable HTTP transport entrypoint (Phase 9b, ADR 0022).

Authenticated the same way as every other endpoint (JWT bearer via
get_current_user) -- MCP's own OAuth-based auth extension is out of
scope for now (documented gap, see ADR 0022). user_id is always the
authenticated caller, never taken from the request body.
"""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.mcp_server import handle_request
from api.models import User

router = APIRouter(tags=["mcp"])


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] | None = None


@router.post("/mcp")
async def mcp_endpoint(
    request: JsonRpcRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await handle_request(request.model_dump(), db=db, user_id=current_user.id)
