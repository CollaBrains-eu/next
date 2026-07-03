"""Preference endpoints (Phase 13, ADR 0028).

Scoped to the caller's own preferences only -- no admin override, unlike
Plan/Decision, since there's no operational need for one here.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import User
from api.preferences import delete_preferences, get_preferences, set_preferences

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesRequest(BaseModel):
    preferred_language: str | None = None


class PreferencesOut(BaseModel):
    preferred_language: str | None


@router.get("/me", response_model=PreferencesOut)
async def get_my_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreferencesOut:
    preferences = await get_preferences(db, user_id=current_user.id)
    return PreferencesOut(preferred_language=preferences.preferred_language if preferences else None)


@router.put("/me", response_model=PreferencesOut)
async def set_my_preferences(
    request: PreferencesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreferencesOut:
    preferences = await set_preferences(db, user_id=current_user.id, preferred_language=request.preferred_language)
    return PreferencesOut(preferred_language=preferences.preferred_language)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    deleted = await delete_preferences(db, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No preferences to delete")
