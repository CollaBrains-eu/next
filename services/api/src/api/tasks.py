"""Task extraction (Planner Agent), manual creation, and listing endpoints.

See ADR 0004 (Task itself) and ADR 0064 (recurrence + due-date
notifications).
"""
from datetime import date, datetime, timedelta
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

TASK_STATUSES = ("open", "in_progress", "done")
RECURRENCE_RULES = ("daily", "weekly", "monthly")


def next_due_date(current: date, recurrence_rule: str) -> date:
    """Advance `current` by one cadence step. Month arithmetic clamps to the
    target month's last day rather than overflowing (e.g. Jan 31 -> Feb 28)."""
    if recurrence_rule == "daily":
        return current + timedelta(days=1)
    if recurrence_rule == "weekly":
        return current + timedelta(days=7)
    if recurrence_rule == "monthly":
        month = current.month + 1
        year = current.year
        if month > 12:
            month = 1
            year += 1
        day = current.day
        while day > 28:
            try:
                return date(year, month, day)
            except ValueError:
                day -= 1
        return date(year, month, day)
    raise ValueError(f"unknown recurrence_rule: {recurrence_rule}")


class TaskOut(BaseModel):
    id: UUID
    document_id: UUID | None
    title: str
    description: str | None
    due_date: date | None
    assignee: str | None
    status: str
    position: int
    source: str
    created_at: datetime
    recurrence_rule: str | None


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


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    due_date: date | None = None
    assignee: str | None = None
    recurrence_rule: str | None = None


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    if body.recurrence_rule is not None and body.recurrence_rule not in RECURRENCE_RULES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"recurrence_rule must be one of: {', '.join(RECURRENCE_RULES)}",
        )
    if body.recurrence_rule is not None and body.due_date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="recurrence_rule requires a due_date")

    task = Task(
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        assignee=body.assignee,
        recurrence_rule=body.recurrence_rule,
        source="manual",
        created_by=current_user.id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


class TaskUpdate(BaseModel):
    status: str
    position: int | None = None
    due_date: date | None = None
    recurrence_rule: str | None = None


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: UUID,
    update: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    if update.status not in TASK_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of: {', '.join(TASK_STATUSES)}",
        )
    if update.recurrence_rule is not None and update.recurrence_rule not in RECURRENCE_RULES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"recurrence_rule must be one of: {', '.join(RECURRENCE_RULES)}",
        )

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    siblings_result = await db.execute(
        select(Task).where(Task.status == update.status, Task.id != task.id).order_by(Task.position)
    )
    siblings = list(siblings_result.scalars().all())

    if update.position is not None:
        target_position = max(0, min(update.position, len(siblings)))
    elif update.status != task.status:
        target_position = len(siblings)
    else:
        target_position = None

    if target_position is not None:
        ordered = siblings[:target_position] + [task] + siblings[target_position:]
        for idx, item in enumerate(ordered):
            if item.position != idx:
                item.position = idx

    # Completing a recurring task spawns its next occurrence as a new row,
    # rather than rolling this one's due_date forward in place -- keeps a
    # real history of completed occurrences instead of silently resetting one.
    if update.status == "done" and task.status != "done" and task.recurrence_rule and task.due_date:
        db.add(
            Task(
                document_id=task.document_id,
                title=task.title,
                description=task.description,
                due_date=next_due_date(task.due_date, task.recurrence_rule),
                assignee=task.assignee,
                source=task.source,
                created_by=task.created_by,
                recurrence_rule=task.recurrence_rule,
            )
        )

    if update.due_date is not None:
        task.due_date = update.due_date
        task.notified_at = None
    if update.recurrence_rule is not None:
        task.recurrence_rule = update.recurrence_rule

    task.status = update.status
    await db.commit()
    await db.refresh(task)
    return task
