"""POST /manager/ask (Phase 11, ADR 0026).

Uses get_effective_user, same as /chat (ADR 0006) -- this lets the
signal-bot service account act on behalf of a linked phone number via
the X-On-Behalf-Of-Phone header (Phase 2 of the unified-chat-consolidation
design, docs/superpowers/specs/2026-07-10-unified-chat-consolidation-design.md).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_effective_user
from api.chat import Citation
from api.db import get_db
from api.legal import DraftResponse
from api.manager_agent import handle_request
from api.models import User

router = APIRouter(prefix="/manager", tags=["manager"])


class AskRequest(BaseModel):
    message: str


class AskResponse(BaseModel):
    answer: str
    tools_called: list[str]
    citations: list[Citation] | None = None
    legal_draft: DraftResponse | None = None


@router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> AskResponse:
    result = await handle_request(db, user_id=current_user.id, role=current_user.role, message=request.message)
    return AskResponse(**result)
