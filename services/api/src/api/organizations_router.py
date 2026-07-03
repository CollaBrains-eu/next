"""Organization policy endpoints (Phase 14, ADR 0029).

admin-role-only: reuses User.role (ADR 0001) rather than a new
org-specific role, since nothing yet distinguishes "admin of this org"
from platform-wide admin -- that's part of the RBAC 2.0 work this phase
doesn't build.
"""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import Organization, User
from api.organizations import get_organization_for_user, set_organization_policies

router = APIRouter(prefix="/organizations", tags=["organizations"])


class PoliciesRequest(BaseModel):
    policies: dict[str, Any]


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    policies: dict[str, Any]


def _require_admin(current_user: User) -> None:
    if current_user.role != "admin":
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
    _require_admin(current_user)
    organization = await _get_org_or_404(db, current_user)
    updated = await set_organization_policies(db, organization_id=organization.id, policies=request.policies)
    return OrganizationOut(id=updated.id, name=updated.name, policies=updated.policies)
