"""Organization policy endpoints (Phase 14, ADR 0029).

Gated by platform-wide admin (User.role, ADR 0001) OR the org's own
`owner_user_id` (ADR 0074, Priority 3) -- the latter lets a self-service
signup manage the org they created without granting them the LDAP-wide
Admin Dashboard. Still not real per-org RBAC (no separate "member" vs
"admin-of-this-org" distinction beyond a single owner) -- that's the
RBAC 2.0 work this phase doesn't build.
"""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import Organization, User
from api.organizations import (
    get_organization_for_user,
    list_organization_members,
    rename_organization,
    set_organization_policies,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


class PoliciesRequest(BaseModel):
    policies: dict[str, Any]


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    policies: dict[str, Any]


def _require_org_admin(current_user: User, organization: Organization) -> None:
    if current_user.role != "admin" and organization.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


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
    _require_org_admin(current_user, organization)
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
    _require_org_admin(current_user, organization)
    updated = await rename_organization(db, organization_id=organization.id, name=body.name)
    return OrganizationOut(id=updated.id, name=updated.name, policies=updated.policies)
