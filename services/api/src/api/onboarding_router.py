"""Public onboarding-link endpoints (Phase 27).

Unauthenticated by design -- the person following the emailed/Signal'd
link doesn't have a session yet. Just enough for a future onboarding
page to check a token's validity and know which account it's for; the
page itself (set a password, register a passkey, etc.) isn't built here.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models import User
from api.onboarding_service import get_valid_onboarding_token

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingTokenOut(BaseModel):
    valid: bool
    user_id: UUID | None = None
    display_name: str | None = None


@router.get("/{token}", response_model=OnboardingTokenOut)
async def check_onboarding_token(token: str, db: AsyncSession = Depends(get_db)) -> OnboardingTokenOut:
    record = await get_valid_onboarding_token(db, token=token)
    if record is None:
        return OnboardingTokenOut(valid=False)
    user = await db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return OnboardingTokenOut(valid=True, user_id=user.id, display_name=user.display_name)
