"""Decision endpoints (Phase 10, ADR 0025)."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.knowledge_graph import get_decision_with_documents
from api.models import Decision, User

router = APIRouter(tags=["decisions"])


class DecisionDocumentOut(BaseModel):
    id: UUID
    title: str


class DecisionOut(BaseModel):
    id: UUID
    summary: str
    plan_id: UUID | None
    created_at: datetime
    supporting_documents: list[DecisionDocumentOut]


class DecisionListItemOut(BaseModel):
    id: UUID
    summary: str


@router.get("/decisions", response_model=list[DecisionListItemOut])
async def list_decisions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Decision]:
    query = select(Decision).order_by(Decision.created_at.desc())
    if current_user.role != "admin":
        query = query.where(Decision.user_id == current_user.id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/decisions/{decision_id}", response_model=DecisionOut)
async def get_decision(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DecisionOut:
    result = await get_decision_with_documents(db, decision_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")

    decision, documents = result
    if decision.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this decision")

    return DecisionOut(
        id=decision.id,
        summary=decision.summary,
        plan_id=decision.plan_id,
        created_at=decision.created_at,
        supporting_documents=[DecisionDocumentOut(id=doc.id, title=doc.title) for doc in documents],
    )
