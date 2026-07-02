"""Task extraction (Planner Agent) and listing endpoints. See ADR 0004."""
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import Document, Task, User
from api.planner_agent import extract_tasks

router = APIRouter(tags=["tasks"])


class TaskOut(BaseModel):
    id: UUID
    document_id: UUID | None
    title: str
    description: str | None
    due_date: date | None
    assignee: str | None
    status: str
    source: str
    created_at: datetime


@router.post("/documents/{document_id}/extract-tasks", response_model=list[TaskOut])
async def extract_tasks_from_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Task]:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.status != "ready" or not document.ocr_text:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Document is not ready yet (status: {document.status})"
        )

    return await extract_tasks(
        db, document_id=document.id, text=document.ocr_text, user_id=current_user.id, source="planner_agent"
    )


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    status_filter: str | None = Query(None, alias="status"),
    document_id: UUID | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Task]:
    query = select(Task).order_by(Task.created_at.desc()).limit(limit).offset(offset)
    if status_filter:
        query = query.where(Task.status == status_filter)
    if document_id:
        query = query.where(Task.document_id == document_id)
    result = await db.execute(query)
    return list(result.scalars().all())


class TaskUpdate(BaseModel):
    status: str


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: UUID,
    update: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    if update.status not in ("open", "done"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be 'open' or 'done'")

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = update.status
    await db.commit()
    await db.refresh(task)
    return task
