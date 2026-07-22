"""Dashboard aggregation endpoints (sub-project 2 of the app-shell redesign)."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.dashboard import get_user_activity
from api.db import get_db
from api.models import User

router = APIRouter(tags=["dashboard"])


class ActivityItemOut(BaseModel):
    type: Literal["document", "task", "case", "entity"]
    id: UUID
    title: str
    created_at: datetime
    link: str


@router.get("/dashboard/activity", response_model=list[ActivityItemOut])
async def get_dashboard_activity(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActivityItemOut]:
    items = await get_user_activity(db, user_id=current_user.id)
    return [
        ActivityItemOut(type=item.type, id=item.id, title=item.title, created_at=item.created_at, link=item.link)
        for item in items
    ]
