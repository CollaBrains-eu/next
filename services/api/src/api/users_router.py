"""Minimal non-admin user lookup (Phase 1 of case/document sharing).

Exact phone-number match only, single result or 404 -- deliberately not
a partial/substring search, so it can't be used to enumerate the user
directory. Reuses admin_service.find_user_by_phone, the same lookup the
admin-only /admin/signal-lookup endpoint already does; this is that same
query opened up to any authenticated user, since a case owner has no
other way to resolve who they want to invite.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.admin_service import find_user_by_phone
from api.auth import get_current_user, validate_phone_number
from api.db import get_db
from api.models import User

router = APIRouter(prefix="/users", tags=["users"])


class UserLookupOut(BaseModel):
    id: UUID
    username: str
    display_name: str


@router.get("/lookup", response_model=UserLookupOut)
async def lookup_user_by_phone(
    phone: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # any authenticated user, not admin-gated
) -> User:
    phone = validate_phone_number(phone)
    user = await find_user_by_phone(db, phone=phone)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user with this phone number")
    return user
