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
from api.cases import (
    add_case_member,
    attach_document_to_case,
    create_case,
    delete_case,
    get_case_dashboard,
    is_case_member,
    link_decision_to_case,
    link_task_to_case,
    link_vehicle_to_case,
    list_case_members,
    list_cases,
    remove_case_member,
    update_case,
)
from api.db import get_db
from api.models import Case, CaseMember, Decision, Document, Task, User, Vehicle

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


class CaseVehicleOut(BaseModel):
    id: UUID
    kenteken: str | None
    merk: str | None
    handelsbenaming: str | None


class CaseDashboardOut(CaseOut):
    documents: list[CaseDocumentOut]
    tasks: list[CaseTaskOut]
    decisions: list[CaseDecisionOut]
    vehicles: list[CaseVehicleOut]


class DocumentCaseRequest(BaseModel):
    case_id: UUID | None = None


def _require_case_owner(case: Case, current_user: User) -> None:
    if case.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this case")


async def _require_case_access(db: AsyncSession, case: Case, current_user: User) -> None:
    """Like `_require_case_owner`, but also lets in anyone granted access
    via `case_members` (e.g. a contractor working someone else's case) --
    ownership stays single-user (`Case.user_id`), membership is additive."""
    if case.user_id == current_user.id or current_user.role == "admin":
        return
    if await is_case_member(db, case_id=case.id, user_id=current_user.id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this case")


class CaseMemberOut(BaseModel):
    id: UUID
    user_id: UUID
    role: str
    created_at: datetime


class CaseMemberCreate(BaseModel):
    user_id: UUID
    role: str = "member"


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
    await _require_case_access(db, case, current_user)

    return CaseDashboardOut(
        id=case.id, name=case.name, description=case.description, status=case.status, created_at=case.created_at,
        documents=[CaseDocumentOut(id=doc.id, title=doc.title) for doc in result["documents"]],
        tasks=[CaseTaskOut(id=task.id, title=task.title, status=task.status) for task in result["tasks"]],
        decisions=[CaseDecisionOut(id=dec.id, summary=dec.summary) for dec in result["decisions"]],
        vehicles=[
            CaseVehicleOut(id=v.id, kenteken=v.kenteken, merk=v.merk, handelsbenaming=v.handelsbenaming)
            for v in result["vehicles"]
        ],
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
    await _require_case_access(db, existing, current_user)

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


@router.put("/documents/{document_id}/case", response_model=CaseDocumentOut)
async def set_document_case_endpoint(
    document_id: UUID,
    request: DocumentCaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseDocumentOut:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this document")

    if request.case_id is not None:
        case = await db.get(Case, request.case_id)
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
        await _require_case_access(db, case, current_user)

    updated = await attach_document_to_case(db, document_id=document_id, case_id=request.case_id)
    return CaseDocumentOut(id=updated.id, title=updated.title)


@router.post("/cases/{case_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def link_task_endpoint(
    case_id: UUID,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    await _require_case_access(db, case, current_user)

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to link this task")

    await link_task_to_case(db, case_id=case_id, task_id=task_id)


@router.post("/cases/{case_id}/decisions/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def link_decision_endpoint(
    case_id: UUID,
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    await _require_case_access(db, case, current_user)

    decision = await db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    if decision.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to link this decision")

    await link_decision_to_case(db, case_id=case_id, decision_id=decision_id)


@router.post("/cases/{case_id}/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def link_vehicle_endpoint(
    case_id: UUID,
    vehicle_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    await _require_case_access(db, case, current_user)

    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    await link_vehicle_to_case(db, case_id=case_id, vehicle_id=vehicle_id)


@router.get("/cases/{case_id}/members", response_model=list[CaseMemberOut])
async def list_case_members_endpoint(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CaseMember]:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    await _require_case_access(db, case, current_user)
    return await list_case_members(db, case_id=case_id)


@router.post("/cases/{case_id}/members", response_model=CaseMemberOut, status_code=status.HTTP_201_CREATED)
async def add_case_member_endpoint(
    case_id: UUID,
    request: CaseMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseMember:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    _require_case_owner(case, current_user)

    member_user = await db.get(User, request.user_id)
    if member_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return await add_case_member(db, case_id=case_id, user_id=request.user_id, role=request.role)


@router.delete("/cases/{case_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_case_member_endpoint(
    case_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    _require_case_owner(case, current_user)

    removed = await remove_case_member(db, case_id=case_id, user_id=user_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
