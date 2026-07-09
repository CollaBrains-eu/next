"""User Facts endpoints (Phase 26). See api/user_facts.py for extraction/conflict logic."""
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_effective_user
from api.db import get_db
from api.models import User, UserFact

router = APIRouter(prefix="/facts", tags=["facts"])


class UserFactOut(BaseModel):
    id: UUID
    user_id: UUID
    fact_type: str
    value: dict
    valid_from: date
    valid_to: date | None
    confidence: float
    status: str
    created_at: datetime


@router.get("", response_model=list[UserFactOut])
async def list_facts(
    fact_type: str | None = Query(None),
    as_of: date | None = Query(None, description="Only facts valid at this point in time"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> list[UserFact]:
    query = select(UserFact).where(UserFact.user_id == current_user.id).order_by(UserFact.valid_from.desc())
    if fact_type:
        query = query.where(UserFact.fact_type == fact_type)
    if as_of is not None:
        query = query.where(
            UserFact.valid_from <= as_of, (UserFact.valid_to.is_(None)) | (UserFact.valid_to >= as_of)
        )
    result = await db.execute(query)
    return list(result.scalars().all())


async def _transition_fact(db: AsyncSession, fact_id: UUID, new_status: str) -> UserFact:
    fact = await db.get(UserFact, fact_id)
    if fact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")
    if fact.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Fact is not pending review (status: {fact.status})"
        )
    fact.status = new_status
    await db.commit()
    await db.refresh(fact)
    return fact


@router.post("/{fact_id}/approve", response_model=UserFactOut)
async def approve_fact(
    fact_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_effective_user),
) -> UserFact:
    return await _transition_fact(db, fact_id, "confirmed")


@router.post("/{fact_id}/reject", response_model=UserFactOut)
async def reject_fact(
    fact_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_effective_user),
) -> UserFact:
    return await _transition_fact(db, fact_id, "rejected")
