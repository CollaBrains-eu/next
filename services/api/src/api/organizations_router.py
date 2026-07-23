"""Organization policy endpoints (Phase 14, ADR 0029).

Gated by platform-wide admin (User.role, ADR 0001) OR the org's own
`owner_user_id` (ADR 0074, Priority 3) -- the latter lets a self-service
signup manage the org they created without granting them the LDAP-wide
Admin Dashboard. Still not real per-org RBAC (no separate "member" vs
"admin-of-this-org" distinction beyond a single owner) -- that's the
RBAC 2.0 work this phase doesn't build.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import EMAIL_PATTERN, get_current_user
from api.db import get_db
from api.invitation_service import (
    create_invitation,
    get_pending_invitation_for_email,
    is_already_a_member,
    list_pending_invitations,
    refresh_invitation,
    revoke_invitation,
    send_invitation_email,
)
from api.models import Invitation, Organization, User
from api.organizations import (
    get_organization_for_user,
    list_organization_members,
    rename_organization,
    require_org_admin,
    set_organization_policies,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


class PoliciesRequest(BaseModel):
    policies: dict[str, Any]


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    policies: dict[str, Any]


async def _get_org_or_404(db: AsyncSession, current_user: User) -> Organization:
    organization = await get_organization_for_user(db, current_user.id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.get("/me", response_model=OrganizationOut)
async def get_my_organization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationOut:
    organization = await _get_org_or_404(db, current_user)
    return OrganizationOut(id=organization.id, name=organization.name, policies=organization.policies)


@router.put("/me/policies", response_model=OrganizationOut)
async def set_my_organization_policies(
    request: PoliciesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationOut:
    organization = await _get_org_or_404(db, current_user)
    require_org_admin(current_user, organization)
    updated = await set_organization_policies(db, organization_id=organization.id, policies=request.policies)
    return OrganizationOut(id=updated.id, name=updated.name, policies=updated.policies)


class OrganizationMemberOut(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: str


@router.get("/me/members", response_model=list[OrganizationMemberOut])
async def list_my_organization_members(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    organization = await _get_org_or_404(db, current_user)
    return await list_organization_members(db, organization.id)


class OrganizationRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


@router.put("/me", response_model=OrganizationOut)
async def rename_my_organization(
    body: OrganizationRenameIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationOut:
    organization = await _get_org_or_404(db, current_user)
    require_org_admin(current_user, organization)
    updated = await rename_organization(db, organization_id=organization.id, name=body.name)
    return OrganizationOut(id=updated.id, name=updated.name, policies=updated.policies)


class InvitationCreateIn(BaseModel):
    email: str


class InvitationOut(BaseModel):
    id: UUID
    email: str
    created_at: datetime
    expires_at: datetime


def _invitation_out(invitation: Invitation) -> InvitationOut:
    return InvitationOut(
        id=invitation.id, email=invitation.email, created_at=invitation.created_at, expires_at=invitation.expires_at
    )


@router.post("/me/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def invite_organization_member(
    body: InvitationCreateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvitationOut:
    """Sends (or, for a still-pending invite to the same address, resends)
    an org invitation by email -- the "invite a stranger" gap ADR 0074
    found missing from cases_router.py/workspace_router.py, which both
    require the invitee to already be a provisioned platform user."""
    organization = await _get_org_or_404(db, current_user)
    require_org_admin(current_user, organization)

    email = body.email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address")

    if await is_already_a_member(db, organization_id=organization.id, email=email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This person is already a member")

    existing = await get_pending_invitation_for_email(db, organization_id=organization.id, email=email)
    invitation = (
        await refresh_invitation(db, invitation=existing)
        if existing is not None
        else await create_invitation(
            db, organization_id=organization.id, email=email, invited_by_user_id=current_user.id
        )
    )

    await send_invitation_email(invitation=invitation, organization_name=organization.name)
    return _invitation_out(invitation)


@router.get("/me/invitations", response_model=list[InvitationOut])
async def list_organization_invitations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InvitationOut]:
    organization = await _get_org_or_404(db, current_user)
    require_org_admin(current_user, organization)
    invitations = await list_pending_invitations(db, organization_id=organization.id)
    return [_invitation_out(invitation) for invitation in invitations]


@router.delete("/me/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_organization_invitation(
    invitation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    organization = await _get_org_or_404(db, current_user)
    require_org_admin(current_user, organization)
    invitation = await revoke_invitation(db, invitation_id=invitation_id, organization_id=organization.id)
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
