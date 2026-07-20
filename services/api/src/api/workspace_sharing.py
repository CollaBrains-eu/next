"""Whole-workspace sharing (v2 parity port -- v2's "werkruimte delen").

Distinct from cases.py (CaseMember, Phase 26), which scopes access to
one case; this scopes to everything an owner owns. Same
pending/accepted/declined invitation shape as case sharing, entity
review, and residency review elsewhere in this codebase.

MAX_ACTIVE_MEMBERS mirrors v2's "maximaal 2 vertrouwde personen" --
counted as pending + accepted (a still-pending invite occupies a slot,
matching v2's own UX of a fixed number of co-admin invites in flight).
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import WorkspaceMember

MAX_ACTIVE_MEMBERS = 2


async def is_workspace_member(db: AsyncSession, *, owner_id: UUID, member_id: UUID) -> bool:
    """True only for an *accepted* membership -- a pending invitation
    doesn't grant access yet."""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.owner_id == owner_id,
            WorkspaceMember.member_id == member_id,
            WorkspaceMember.status == "accepted",
        )
    )
    return result.scalar_one_or_none() is not None


async def can_export_workspace(db: AsyncSession, *, owner_id: UUID, member_id: UUID) -> bool:
    """True only for an accepted membership with can_export explicitly granted."""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.owner_id == owner_id,
            WorkspaceMember.member_id == member_id,
            WorkspaceMember.status == "accepted",
            WorkspaceMember.can_export.is_(True),
        )
    )
    return result.scalar_one_or_none() is not None


async def list_workspace_members(db: AsyncSession, *, owner_id: UUID) -> list[WorkspaceMember]:
    """People an owner has invited into their workspace (any status)."""
    result = await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.owner_id == owner_id).order_by(WorkspaceMember.created_at)
    )
    return list(result.scalars().all())


async def list_pending_workspace_invitations(db: AsyncSession, *, member_id: UUID) -> list[WorkspaceMember]:
    """Invitations sent to this user, awaiting their response."""
    result = await db.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.member_id == member_id, WorkspaceMember.status == "pending")
        .order_by(WorkspaceMember.created_at)
    )
    return list(result.scalars().all())


async def list_shared_workspaces(db: AsyncSession, *, member_id: UUID) -> list[WorkspaceMember]:
    """Workspaces this user has accepted an invitation into."""
    result = await db.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.member_id == member_id, WorkspaceMember.status == "accepted")
        .order_by(WorkspaceMember.created_at)
    )
    return list(result.scalars().all())


async def add_workspace_member(
    db: AsyncSession, *, owner_id: UUID, member_id: UUID, can_export: bool = False
) -> WorkspaceMember:
    """Invites a user into the owner's workspace -- creates a `pending`
    invitation, doesn't grant access until accepted. Re-inviting someone
    whose invitation was declined resets it back to pending.

    Raises ValueError if the owner already has MAX_ACTIVE_MEMBERS
    pending-or-accepted memberships and this would be a new one.
    """
    existing = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.owner_id == owner_id, WorkspaceMember.member_id == member_id
        )
    )
    member = existing.scalar_one_or_none()
    if member is not None:
        member.can_export = can_export
        member.status = "pending"
        await db.commit()
        await db.refresh(member)
        return member

    active_result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.owner_id == owner_id, WorkspaceMember.status.in_(("pending", "accepted"))
        )
    )
    if len(active_result.scalars().all()) >= MAX_ACTIVE_MEMBERS:
        raise ValueError(f"A workspace can have at most {MAX_ACTIVE_MEMBERS} shared members")

    member = WorkspaceMember(owner_id=owner_id, member_id=member_id, can_export=can_export, status="pending")
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def respond_to_workspace_invitation(
    db: AsyncSession, *, owner_id: UUID, member_id: UUID, accept: bool
) -> WorkspaceMember | None:
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.owner_id == owner_id,
            WorkspaceMember.member_id == member_id,
            WorkspaceMember.status == "pending",
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        return None
    member.status = "accepted" if accept else "declined"
    await db.commit()
    await db.refresh(member)
    return member


async def set_workspace_member_can_export(
    db: AsyncSession, *, owner_id: UUID, member_id: UUID, can_export: bool
) -> WorkspaceMember | None:
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.owner_id == owner_id, WorkspaceMember.member_id == member_id
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        return None
    member.can_export = can_export
    await db.commit()
    await db.refresh(member)
    return member


async def remove_workspace_member(db: AsyncSession, *, owner_id: UUID, member_id: UUID) -> bool:
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.owner_id == owner_id, WorkspaceMember.member_id == member_id
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        return False
    await db.delete(member)
    await db.commit()
    return True
