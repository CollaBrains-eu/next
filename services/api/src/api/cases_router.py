"""Case/Matter workspace CRUD + dashboard endpoints (Phase 16).

Ownership check pattern copied exactly from api/decisions.py: a case's
user_id (or admin role) gates all access to it. Document/task/decision
attach-to-case endpoints live in Task 4 of this same file.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.cases import create_case, delete_case, get_case_dashboard, list_cases, update_case
from api.db import get_db
from api.models import Case, User

router = APIRouter(tags=["cases"])


class CaseCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class CaseUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    status: str | None = None


class CaseOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime


class CaseDocumentOut(BaseModel):
    id: UUID
    title: str


class CaseTaskOut(BaseModel):
    id: UUID
    title: str
    status: str


class CaseDecisionOut(BaseModel):
    id: UUID
    summary: str


class CaseDashboardOut(CaseOut):
    documents: list[CaseDocumentOut]
    tasks: list[CaseTaskOut]
    decisions: list[CaseDecisionOut]


def _require_case_owner(case: Case, current_user: User) -> None:
    if case.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this case")


@router.post("/cases", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case_endpoint(
    request: CaseCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Case:
    return await create_case(db, user_id=current_user.id, name=request.name, description=request.description)


@router.get("/cases", response_model=list[CaseOut])
async def list_cases_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Case]:
    return await list_cases(db, user_id=current_user.id)


@router.get("/cases/{case_id}", response_model=CaseDashboardOut)
async def get_case_endpoint(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseDashboardOut:
    result: dict[str, Any] | None = await get_case_dashboard(db, case_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    case = result["case"]
    _require_case_owner(case, current_user)

    return CaseDashboardOut(
        id=case.id, name=case.name, description=case.description, status=case.status, created_at=case.created_at,
        documents=[CaseDocumentOut(id=doc.id, title=doc.title) for doc in result["documents"]],
        tasks=[CaseTaskOut(id=task.id, title=task.title, status=task.status) for task in result["tasks"]],
        decisions=[CaseDecisionOut(id=dec.id, summary=dec.summary) for dec in result["decisions"]],
    )


@router.patch("/cases/{case_id}", response_model=CaseOut)
async def update_case_endpoint(
    case_id: UUID,
    request: CaseUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Case:
    existing = await db.get(Case, case_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    _require_case_owner(existing, current_user)

    if request.status is not None and request.status not in ("open", "closed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be 'open' or 'closed'")

    updated = await update_case(
        db, case_id=case_id, name=request.name, description=request.description, status_value=request.status,
    )
    return updated


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case_endpoint(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    existing = await db.get(Case, case_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    _require_case_owner(existing, current_user)
    await delete_case(db, case_id=case_id)
