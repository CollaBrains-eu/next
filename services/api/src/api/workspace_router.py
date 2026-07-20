"""Whole-workspace sharing endpoints (v2 parity port -- v2's "werkruimte
delen"). See workspace_sharing.py for the underlying service functions.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import User, WorkspaceMember
from api.workspace_sharing import (
    add_workspace_member,
    list_pending_workspace_invitations,
    list_shared_workspaces,
    list_workspace_members,
    remove_workspace_member,
    respond_to_workspace_invitation,
    set_workspace_member_can_export,
)

router = APIRouter(prefix="/workspace", tags=["workspace"])


class WorkspaceMemberOut(BaseModel):
    id: UUID
    owner_id: UUID
    owner_username: str
    owner_display_name: str
    member_id: UUID
    member_username: str
    member_display_name: str
    can_export: bool
    status: str
    created_at: datetime


class WorkspaceMemberCreate(BaseModel):
    user_id: UUID
    can_export: bool = False


class WorkspaceMemberUpdate(BaseModel):
    can_export: bool


async def _workspace_member_out(db: AsyncSession, member: WorkspaceMember) -> WorkspaceMemberOut:
    owner = await db.get(User, member.owner_id)
    invitee = await db.get(User, member.member_id)
    return WorkspaceMemberOut(
        id=member.id,
        owner_id=member.owner_id, owner_username=owner.username, owner_display_name=owner.display_name,
        member_id=member.member_id, member_username=invitee.username, member_display_name=invitee.display_name,
        can_export=member.can_export, status=member.status, created_at=member.created_at,
    )


@router.get("/members", response_model=list[WorkspaceMemberOut])
async def list_my_workspace_members(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkspaceMemberOut]:
    """People the current user has invited into their own workspace."""
    members = await list_workspace_members(db, owner_id=current_user.id)
    return [await _workspace_member_out(db, m) for m in members]


@router.post("/members", response_model=WorkspaceMemberOut, status_code=status.HTTP_201_CREATED)
async def invite_workspace_member(
    request: WorkspaceMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceMemberOut:
    if request.user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot share your workspace with yourself")

    invitee = await db.get(User, request.user_id)
    if invitee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        member = await add_workspace_member(
            db, owner_id=current_user.id, member_id=request.user_id, can_export=request.can_export
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return await _workspace_member_out(db, member)


@router.patch("/members/{member_id}", response_model=WorkspaceMemberOut)
async def update_workspace_member(
    member_id: UUID,
    request: WorkspaceMemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceMemberOut:
    member = await set_workspace_member_can_export(
        db, owner_id=current_user.id, member_id=member_id, can_export=request.can_export
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    return await _workspace_member_out(db, member)


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_workspace_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    removed = await remove_workspace_member(db, owner_id=current_user.id, member_id=member_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")


@router.get("/invitations", response_model=list[WorkspaceMemberOut])
async def list_my_pending_invitations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkspaceMemberOut]:
    """Workspace-sharing invitations sent to the current user, awaiting response."""
    members = await list_pending_workspace_invitations(db, member_id=current_user.id)
    return [await _workspace_member_out(db, m) for m in members]


@router.get("/shared-with-me", response_model=list[WorkspaceMemberOut])
async def list_workspaces_shared_with_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkspaceMemberOut]:
    """Workspaces the current user has accepted an invitation into."""
    members = await list_shared_workspaces(db, member_id=current_user.id)
    return [await _workspace_member_out(db, m) for m in members]


@router.post("/invitations/{owner_id}/accept", response_model=WorkspaceMemberOut)
async def accept_workspace_invitation(
    owner_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceMemberOut:
    member = await respond_to_workspace_invitation(db, owner_id=owner_id, member_id=current_user.id, accept=True)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending invitation found")
    return await _workspace_member_out(db, member)


@router.post("/invitations/{owner_id}/decline", response_model=WorkspaceMemberOut)
async def decline_workspace_invitation(
    owner_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkspaceMemberOut:
    member = await respond_to_workspace_invitation(db, owner_id=owner_id, member_id=current_user.id, accept=False)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending invitation found")
    return await _workspace_member_out(db, member)
