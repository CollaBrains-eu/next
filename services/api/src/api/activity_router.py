"""GET /activity -- read endpoint for the audit log (api/activity.py)."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.activity import list_activity
from api.auth import get_current_user
from api.cases_router import _require_case_access
from api.db import get_db
from api.documents import _can_read_document
from api.models import Case, Document, Task, User
from api.tasks import _can_access_task

router = APIRouter(tags=["activity"])
EntityType = Literal["document", "case", "task"]


class ActivityLogEntryOut(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    actor_user_id: UUID
    actor_display_name: str
    detail: dict
    created_at: datetime


async def _require_entity_read_access(db: AsyncSession, entity_type: EntityType, entity_id: UUID, current_user: User) -> None:
    if entity_type == "document":
        document = await db.get(Document, entity_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if not await _can_read_document(db, document, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this document")
    elif entity_type == "case":
        case = await db.get(Case, entity_id)
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
        await _require_case_access(db, case, current_user)
    else:
        task = await db.get(Task, entity_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        if not await _can_access_task(db, task, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this task")


@router.get("/activity", response_model=list[ActivityLogEntryOut])
async def list_activity_endpoint(
    entity_type: EntityType = Query(...),
    entity_id: UUID = Query(...),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActivityLogEntryOut]:
    await _require_entity_read_access(db, entity_type, entity_id, current_user)
    entries = await list_activity(db, entity_type=entity_type, entity_id=entity_id, limit=limit, offset=offset)

    actor_ids = {entry.actor_user_id for entry in entries}
    actors: dict[UUID, User] = {}
    for actor_id in actor_ids:
        actor = await db.get(User, actor_id)
        if actor is not None:
            actors[actor_id] = actor

    return [
        ActivityLogEntryOut(
            id=entry.id, entity_type=entry.entity_type, entity_id=entry.entity_id, action=entry.action,
            actor_user_id=entry.actor_user_id,
            actor_display_name=actors[entry.actor_user_id].display_name if entry.actor_user_id in actors else "",
            detail=entry.detail, created_at=entry.created_at,
        )
        for entry in entries
    ]
