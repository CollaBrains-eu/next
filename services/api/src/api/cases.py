"""Case/Matter workspace domain logic (Phase 16).

Documents link to a Case via a direct case_id FK (the most central,
most-queried relationship); tasks and decisions link via the existing
polymorphic GraphEdge table (Phase 10, ADR 0025) rather than new columns
on their own tables. None of these functions check ownership -- that's
the router's job (api/cases_router.py), matching the existing split
between api/knowledge_graph.py (no ownership checks) and
api/decisions.py (checks ownership before calling it).
"""
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Case, Decision, Document, GraphEdge, Task


async def create_case(db: AsyncSession, *, user_id: UUID, name: str, description: str | None = None) -> Case:
    case = Case(user_id=user_id, name=name, description=description)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


async def list_cases(db: AsyncSession, *, user_id: UUID) -> list[Case]:
    result = await db.execute(select(Case).where(Case.user_id == user_id).order_by(Case.created_at.desc()))
    return list(result.scalars().all())


async def update_case(
    db: AsyncSession, *, case_id: UUID, name: str | None = None, description: str | None = None,
    status_value: str | None = None,
) -> Case | None:
    case = await db.get(Case, case_id)
    if case is None:
        return None
    if name is not None:
        case.name = name
    if description is not None:
        case.description = description
    if status_value is not None:
        case.status = status_value
    await db.commit()
    await db.refresh(case)
    return case


async def delete_case(db: AsyncSession, *, case_id: UUID) -> bool:
    case = await db.get(Case, case_id)
    if case is None:
        return False

    edges_result = await db.execute(
        select(GraphEdge).where(GraphEdge.target_type == "case", GraphEdge.target_id == case_id)
    )
    for edge in edges_result.scalars().all():
        await db.delete(edge)

    await db.delete(case)
    await db.commit()
    return True


async def attach_document_to_case(db: AsyncSession, *, document_id: UUID, case_id: UUID | None) -> Document | None:
    document = await db.get(Document, document_id)
    if document is None:
        return None
    document.case_id = case_id
    await db.commit()
    await db.refresh(document)
    return document


async def link_task_to_case(db: AsyncSession, *, case_id: UUID, task_id: UUID) -> bool:
    case = await db.get(Case, case_id)
    task = await db.get(Task, task_id)
    if case is None or task is None:
        return False
    db.add(GraphEdge(
        source_type="task", source_id=task.id, target_type="case", target_id=case.id,
        relationship_type="belongs_to",
    ))
    await db.commit()
    return True


async def link_decision_to_case(db: AsyncSession, *, case_id: UUID, decision_id: UUID) -> bool:
    case = await db.get(Case, case_id)
    decision = await db.get(Decision, decision_id)
    if case is None or decision is None:
        return False
    db.add(GraphEdge(
        source_type="decision", source_id=decision.id, target_type="case", target_id=case.id,
        relationship_type="belongs_to",
    ))
    await db.commit()
    return True


async def get_case_dashboard(db: AsyncSession, case_id: UUID) -> dict[str, Any] | None:
    case = await db.get(Case, case_id)
    if case is None:
        return None

    documents_result = await db.execute(select(Document).where(Document.case_id == case_id))
    documents = list(documents_result.scalars().all())

    edges_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.target_type == "case", GraphEdge.target_id == case_id,
            GraphEdge.relationship_type == "belongs_to",
        )
    )
    edges = list(edges_result.scalars().all())
    task_ids = [edge.source_id for edge in edges if edge.source_type == "task"]
    decision_ids = [edge.source_id for edge in edges if edge.source_type == "decision"]

    tasks: list[Task] = []
    if task_ids:
        tasks_result = await db.execute(select(Task).where(Task.id.in_(task_ids)))
        tasks = list(tasks_result.scalars().all())

    decisions: list[Decision] = []
    if decision_ids:
        decisions_result = await db.execute(select(Decision).where(Decision.id.in_(decision_ids)))
        decisions = list(decisions_result.scalars().all())

    return {"case": case, "documents": documents, "tasks": tasks, "decisions": decisions}
