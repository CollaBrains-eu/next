"""POST /feedback (Phase 28, answer-quality signal).

Captures whether a user found a grounded answer useful, alongside the
reflection verdict already computed for that same answer -- see
docs/superpowers/specs/2026-07-18-answer-quality-signal-design.md. No
new LLM call: reflection_confidence/reflection_sufficient_evidence are
just round-tripped back from the chat response that produced them.
"""
from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import AnswerFeedback, User

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    endpoint: str
    question: str
    answer: str
    rating: Literal["up", "down"]
    reflection_confidence: int | None = None
    reflection_sufficient_evidence: bool | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: FeedbackIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    db.add(AnswerFeedback(user_id=current_user.id, **body.model_dump()))
    await db.commit()
