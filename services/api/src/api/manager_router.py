"""POST /manager/ask (Phase 11, ADR 0026).

Uses get_current_user, not get_effective_user -- unlike /chat, there's
no established Signal on-behalf-of caller for this endpoint yet.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.manager_agent import handle_request
from api.models import User

router = APIRouter(prefix="/manager", tags=["manager"])


class AskRequest(BaseModel):
    message: str


class AskResponse(BaseModel):
    answer: str
    tools_called: list[str]


@router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AskResponse:
    result = await handle_request(db, user_id=current_user.id, role=current_user.role, message=request.message)
    return AskResponse(**result)
