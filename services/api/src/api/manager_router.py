"""POST /manager/ask (Phase 11, ADR 0026) and POST /manager/reason
(docs/deployment/ai-optimization.md).

Uses get_effective_user, same as /chat (ADR 0006) -- this lets the
signal-bot service account act on behalf of a linked phone number via
the X-On-Behalf-Of-Phone header (Phase 2 of the unified-chat-consolidation
design, docs/superpowers/specs/2026-07-10-unified-chat-consolidation-design.md).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import execute_complex_reasoning
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


class ReasonRequest(BaseModel):
    prompt: str


class ReasonResponse(BaseModel):
    thinking: str
    solution: str


@router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> AskResponse:
    result = await handle_request(db, user_id=current_user.id, role=current_user.role, message=request.message)
    return AskResponse(**result)


@router.post("/reason", response_model=ReasonResponse)
async def reason(
    request: ReasonRequest,
    current_user: User = Depends(get_effective_user),
) -> ReasonResponse:
    """Complex-reasoning path (deepseek-r1, settings.reasoning_model) -- deliberately
    bypasses manager_agent's tool-calling loop, since this is for logic/reasoning
    prompts, not document-grounded or tool-driven requests. `thinking` is included
    for admin/debug visibility only; frontend callers should show `solution`.
    """
    result = await execute_complex_reasoning(request.prompt, user_id=current_user.id, endpoint="manager_reason")
    return ReasonResponse(**result)
