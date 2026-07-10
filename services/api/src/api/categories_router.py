"""Category taxonomy lookup (Phase 24, document-categories plan Task 3).

Read-only endpoint for the frontend's category filter UI. `CategoryOut`
deliberately omits `name` -- the seed data's `name` column is just the
English slug repeated (see the `0026aa5966bf` migration), and the
frontend derives the display label from `slug` via i18n
(apps/web/src/locales/{en,nl,de}.json under the "categories" namespace).
Shipping the placeholder `name` over the wire would invite it to be
rendered by mistake instead of the localized label.
"""
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import Category, User

router = APIRouter(tags=["categories"])


class CategoryOut(BaseModel):
    id: UUID
    slug: str
    icon: str | None
    color: str | None
    parent_id: UUID | None


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    category_type: str = "document",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Category]:
    result = await db.execute(
        select(Category).where(Category.category_type == category_type).order_by(Category.name)
    )
    return list(result.scalars().all())
