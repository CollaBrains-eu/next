"""Memory listing and manual deletion endpoints (Phase 8b, ADR 0018).

Retrieval-by-similarity and automatic creation from chat live in
`api/memory.py` and are wired into `api/chat.py`; this router is just
direct user-facing management of a user's own memory rows.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.memory import delete_memory
from api.models import Memory, User

router = APIRouter(tags=["memories"])


class MemoryOut(BaseModel):
    id: UUID
    memory_type: str
    importance: int
    summary: str
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None


@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(
    memory_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Memory]:
    query = (
        select(Memory)
        .where(Memory.user_id == current_user.id)
        .order_by(Memory.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if memory_type:
        query = query.where(Memory.memory_type == memory_type)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_endpoint(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    deleted = await delete_memory(
        db, memory_id=memory_id, user_id=current_user.id, is_admin=current_user.role == "admin"
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
