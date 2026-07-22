"""POST /share (create/rotate) + GET /share/{token} (resolve, login required).

Login is required to resolve a token (see `get_current_user` dependency
below) -- this is not anonymous access, it's a bypass of the entity's own
ownership/membership check for whoever holds the link. The resolve
response is a read-only detail snapshot only; it does not extend to an
entity's other action endpoints (download/summarize/attach/delete), which
keep their own independent ownership checks.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.cases_router import _build_case_dashboard_out, _require_case_owner
from api.config import settings
from api.db import get_db
from api.documents import _build_document_detail_out, _require_document_owner
from api.models import Case, Document, Task, User
from api.sharing import create_or_rotate_share_link, get_valid_share_link
from api.tasks import TaskOut, _can_access_task

router = APIRouter(tags=["sharing"])
EntityType = Literal["document", "case", "task"]


class ShareLinkCreateRequest(BaseModel):
    entity_type: EntityType
    entity_id: UUID


class ShareLinkOut(BaseModel):
    token: str
    url: str
    expires_at: datetime


class ShareResolveOut(BaseModel):
    entity_type: EntityType
    data: dict


async def _require_entity_manage_access(db: AsyncSession, entity_type: EntityType, entity_id: UUID, current_user: User) -> None:
    if entity_type == "document":
        document = await db.get(Document, entity_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        _require_document_owner(document, current_user)
    elif entity_type == "case":
        case = await db.get(Case, entity_id)
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
        _require_case_owner(case, current_user)
    else:
        task = await db.get(Task, entity_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        if not await _can_access_task(db, task, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to share this task")


@router.post("/share", response_model=ShareLinkOut, status_code=status.HTTP_201_CREATED)
async def create_share_link_endpoint(
    request: ShareLinkCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShareLinkOut:
    await _require_entity_manage_access(db, request.entity_type, request.entity_id, current_user)
    link = await create_or_rotate_share_link(
        db, entity_type=request.entity_type, entity_id=request.entity_id, created_by_user_id=current_user.id,
    )
    return ShareLinkOut(token=link.token, url=f"{settings.app_base_url}/share/{link.token}", expires_at=link.expires_at)


@router.get("/share/{token}", response_model=ShareResolveOut)
async def resolve_share_link(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # login required -- NOT anonymous access
) -> ShareResolveOut:
    link = await get_valid_share_link(db, token=token)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found or expired")

    if link.entity_type == "document":
        document = await db.get(Document, link.entity_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document no longer exists")
        data = await _build_document_detail_out(db, document)
        payload = data.model_dump(mode="json")
    elif link.entity_type == "case":
        case = await db.get(Case, link.entity_id)
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case no longer exists")
        data = await _build_case_dashboard_out(db, case.id, current_user)
        payload = data.model_dump(mode="json")
    else:
        task = await db.get(Task, link.entity_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task no longer exists")
        payload = jsonable_encoder(TaskOut.model_validate(task, from_attributes=True))

    return ShareResolveOut(entity_type=link.entity_type, data=payload)
