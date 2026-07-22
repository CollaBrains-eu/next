"""Task extraction (Planner Agent), manual creation, and listing endpoints.

See ADR 0004 (Task itself) and ADR 0064 (recurrence + due-date
notifications).
"""
from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.calendar_sync import sync_appointment_for_task
from api.db import get_db
from api.documents import _can_read_document
from api.ics_utils import build_vevent_calendar, format_ics_date, ics_slug
from api.models import CaseMember, Document, Task, TASK_CATEGORIES, User
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
    category: str | None


async def _can_access_task(db: AsyncSession, task: Task, current_user: User) -> bool:
    """Creator and admin always can; a document-linked task extends the same
    access `_can_read_document` already grants on that document (owner or
    accepted case member) -- a task inherits its document's sharing rather
    than having a separate permission model."""
    if task.created_by == current_user.id or current_user.role == "admin":
        return True
    if task.document_id is not None:
        document = await db.get(Document, task.document_id)
        if document is not None:
            return await _can_read_document(db, document, current_user)
    return False


@router.post("/documents/{document_id}/extract-tasks", response_model=list[TaskOut])
async def extract_tasks_from_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Task]:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not await _can_read_document(db, document, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this document")
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
    if current_user.role != "admin":
        member_exists = exists(
            select(CaseMember.id).where(
                CaseMember.case_id == Document.case_id,
                CaseMember.user_id == current_user.id,
                CaseMember.status == "accepted",
            )
        )
        query = query.outerjoin(Document, Task.document_id == Document.id).where(
            or_(
                Task.created_by == current_user.id,
                Document.owner_id == current_user.id,
                member_exists,
            )
        )
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
    category: str | None = None


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
    if body.category is not None and body.category not in TASK_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"category must be one of: {', '.join(TASK_CATEGORIES)}",
        )

    task = Task(
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        assignee=body.assignee,
        recurrence_rule=body.recurrence_rule,
        category=body.category,
        source="manual",
        created_by=current_user.id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await sync_appointment_for_task(db, task=task, user_id=current_user.id)
    return task


class TaskUpdate(BaseModel):
    status: str
    position: int | None = None
    due_date: date | None = None
    recurrence_rule: str | None = None
    category: str | None = None


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
    if update.category is not None and update.category not in TASK_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"category must be one of: {', '.join(TASK_CATEGORIES)}",
        )

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if not await _can_access_task(db, task, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this task")

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
    spawned_task: Task | None = None
    if update.status == "done" and task.status != "done" and task.recurrence_rule and task.due_date:
        spawned_task = Task(
            document_id=task.document_id,
            title=task.title,
            description=task.description,
            due_date=next_due_date(task.due_date, task.recurrence_rule),
            assignee=task.assignee,
            source=task.source,
            created_by=task.created_by,
            recurrence_rule=task.recurrence_rule,
            category=task.category,
        )
        db.add(spawned_task)

    if update.due_date is not None:
        task.due_date = update.due_date
        task.notified_at = None
    if update.recurrence_rule is not None:
        task.recurrence_rule = update.recurrence_rule
    if update.category is not None:
        task.category = update.category

    task.status = update.status
    await db.commit()
    await db.refresh(task)
    await sync_appointment_for_task(db, task=task, user_id=current_user.id)
    if spawned_task is not None:
        await db.refresh(spawned_task)
        await sync_appointment_for_task(db, task=spawned_task, user_id=current_user.id)
    return task


@router.get("/tasks/{task_id}/ics")
async def export_task_ics(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """All-day VEVENT built from the task's due_date. Tasks (unlike
    Appointments) have no time-of-day, so this always emits a
    DTSTART;VALUE=DATE event rather than a timed one."""
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if not await _can_access_task(db, task, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this task")
    if task.due_date is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task has no due date to export")

    ics_text = build_vevent_calendar(
        uid=str(task.id),
        summary=task.title,
        dtstart=format_ics_date(task.due_date),
        all_day=True,
        description=task.description,
        prodid="-//CollaBrains//Tasks//EN",
    )
    slug = ics_slug(task.title)
    return Response(
        content=ics_text,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{slug}.ics"'},
    )
