"""Public/authenticated org-invitation endpoints (Priority 3, ADR 0074).

Recipient side, keyed by the invitation's own token -- works before the
invitee has any session at all. The sender side (an org admin/owner
creating, listing, and revoking invitations their org has sent) lives in
organizations_router.py under /organizations/me/invitations instead,
since that's scoped by the caller's own org membership.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import Token, create_access_token, get_current_user
from api.db import get_db
from api.invitation_service import accept_invitation_for_existing_user, get_valid_invitation
from api.models import Organization, User

router = APIRouter(prefix="/invitations", tags=["invitations"])


class InvitationCheckOut(BaseModel):
    valid: bool
    organization_name: str | None = None
    email: str | None = None
    account_exists: bool = False


@router.get("/{token}", response_model=InvitationCheckOut)
async def check_invitation(token: str, db: AsyncSession = Depends(get_db)) -> InvitationCheckOut:
    """Unauthenticated by design, same as onboarding_router.py's token
    check -- lets a future invitation-landing page decide whether to show
    a login form (account_exists) or a registration form before the
    invitee has any session."""
    invitation = await get_valid_invitation(db, token=token)
    if invitation is None:
        return InvitationCheckOut(valid=False)

    organization = await db.get(Organization, invitation.organization_id)
    existing_user = await db.execute(select(User).where(User.email == invitation.email))
    account_exists = existing_user.scalar_one_or_none() is not None

    return InvitationCheckOut(
        valid=True,
        organization_name=organization.name if organization is not None else None,
        email=invitation.email,
        account_exists=account_exists,
    )


@router.post("/{token}/accept", response_model=Token)
async def accept_invitation(
    token: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Token:
    """For someone who already has an account and is logged in -- switches
    them into the inviting org. A brand-new invitee instead calls
    /auth/register with this same token and never hits this endpoint."""
    invitation = await accept_invitation_for_existing_user(db, token=token, user=current_user)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation is invalid or has expired"
        )
    return Token(access_token=create_access_token(current_user.username, current_user.role))
