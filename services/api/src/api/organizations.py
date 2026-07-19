"""Organizations: the tenant boundary (Phase 14, ADR 0029).

Only organizational membership and one real policy exist so far --
approval_required_goals, overriding planning_engine.APPROVAL_REQUIRED_GOALS
per organization. A full per-table organization_id retrofit and adversarial
tenant isolation are explicitly deferred; see the ADR for why.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Organization, User


async def get_organization_for_user(db: AsyncSession, user_id: UUID) -> Organization | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    return await db.get(Organization, user.organization_id)


async def list_organization_members(db: AsyncSession, organization_id: UUID) -> list[User]:
    result = await db.execute(
        select(User).where(User.organization_id == organization_id).order_by(User.username)
    )
    return list(result.scalars().all())


async def rename_organization(db: AsyncSession, *, organization_id: UUID, name: str) -> Organization:
    organization = await db.get(Organization, organization_id)
    if organization is None:
        raise ValueError(f"unknown organization: {organization_id}")
    organization.name = name
    await db.commit()
    await db.refresh(organization)
    return organization


async def get_approval_required_goals(
    db: AsyncSession, user_id: UUID, *, default: frozenset[str]
) -> frozenset[str]:
    """The calling user's organization's override of the platform default, if set."""
    organization = await get_organization_for_user(db, user_id)
    if organization is None:
        return default
    override = organization.policies.get("approval_required_goals")
    if not isinstance(override, list) or not all(isinstance(item, str) for item in override):
        return default
    return frozenset(override)


async def set_organization_policies(db: AsyncSession, *, organization_id: UUID, policies: dict) -> Organization:
    organization = await db.get(Organization, organization_id)
    if organization is None:
        raise ValueError(f"unknown organization: {organization_id}")
    organization.policies = policies
    await db.commit()
    await db.refresh(organization)
    return organization
