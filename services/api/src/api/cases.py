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

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Appointment, Case, CaseMember, Decision, Document, GraphEdge, Task, Vehicle


async def create_case(db: AsyncSession, *, user_id: UUID, name: str, description: str | None = None) -> Case:
    case = Case(user_id=user_id, name=name, description=description)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


async def list_cases(db: AsyncSession, *, user_id: UUID) -> list[Case]:
    """Cases the user owns, plus cases where they're an *accepted* member --
    a pending invitation doesn't put the case in this list (see
    list_pending_invitations for those)."""
    result = await db.execute(
        select(Case)
        .outerjoin(CaseMember, CaseMember.case_id == Case.id)
        .where(
            or_(
                Case.user_id == user_id,
                (CaseMember.user_id == user_id) & (CaseMember.status == "accepted"),
            )
        )
        .order_by(Case.created_at.desc())
        .distinct()
    )
    return list(result.scalars().all())


async def list_cases_with_counts(db: AsyncSession, *, user_id: UUID) -> list[tuple[Case, int, int]]:
    """Like list_cases, but each row also carries its document_count and
    (accepted-only) member_count -- for the Cases list view, which needs
    both numbers cheaply rather than N+1 queries per case."""
    document_counts = (
        select(Document.case_id, func.count().label("n"))
        .where(Document.case_id.is_not(None))
        .group_by(Document.case_id)
        .subquery()
    )
    member_counts = (
        select(CaseMember.case_id, func.count().label("n"))
        .where(CaseMember.status == "accepted")
        .group_by(CaseMember.case_id)
        .subquery()
    )
    result = await db.execute(
        select(Case, func.coalesce(document_counts.c.n, 0), func.coalesce(member_counts.c.n, 0))
        .outerjoin(document_counts, document_counts.c.case_id == Case.id)
        .outerjoin(member_counts, member_counts.c.case_id == Case.id)
        .outerjoin(CaseMember, CaseMember.case_id == Case.id)
        .where(
            or_(
                Case.user_id == user_id,
                (CaseMember.user_id == user_id) & (CaseMember.status == "accepted"),
            )
        )
        .order_by(Case.created_at.desc())
        .distinct()
    )
    return [(case, doc_count, member_count) for case, doc_count, member_count in result.all()]


async def get_case_counts(db: AsyncSession, *, case_id: UUID) -> tuple[int, int]:
    """(document_count, accepted-member_count) for a single case -- used
    wherever a CaseOut is built outside the bulk list_cases_with_counts
    query (create/update endpoints)."""
    document_count = (
        await db.execute(select(func.count()).select_from(Document).where(Document.case_id == case_id))
    ).scalar_one()
    member_count = (
        await db.execute(
            select(func.count())
            .select_from(CaseMember)
            .where(CaseMember.case_id == case_id, CaseMember.status == "accepted")
        )
    ).scalar_one()
    return document_count, member_count


async def is_case_member(db: AsyncSession, *, case_id: UUID, user_id: UUID) -> bool:
    """True only for an *accepted* membership -- a pending invitation
    doesn't grant access yet."""
    result = await db.execute(
        select(CaseMember).where(
            CaseMember.case_id == case_id, CaseMember.user_id == user_id, CaseMember.status == "accepted"
        )
    )
    return result.scalar_one_or_none() is not None


async def list_case_members(db: AsyncSession, *, case_id: UUID) -> list[CaseMember]:
    result = await db.execute(
        select(CaseMember).where(CaseMember.case_id == case_id).order_by(CaseMember.created_at)
    )
    return list(result.scalars().all())


async def list_pending_invitations(db: AsyncSession, *, user_id: UUID) -> list[CaseMember]:
    result = await db.execute(
        select(CaseMember)
        .where(CaseMember.user_id == user_id, CaseMember.status == "pending")
        .order_by(CaseMember.created_at)
    )
    return list(result.scalars().all())


async def add_case_member(db: AsyncSession, *, case_id: UUID, user_id: UUID, role: str = "member") -> CaseMember:
    """Invites a user to a case -- creates a `pending` invitation, it
    doesn't grant access until the invited user accepts (see
    accept_case_member). Re-inviting someone whose invitation was
    declined resets it back to pending with the new role."""
    existing = await db.execute(
        select(CaseMember).where(CaseMember.case_id == case_id, CaseMember.user_id == user_id)
    )
    member = existing.scalar_one_or_none()
    if member is not None:
        member.role = role
        member.status = "pending"
        await db.commit()
        await db.refresh(member)
        return member

    member = CaseMember(case_id=case_id, user_id=user_id, role=role, status="pending")
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def respond_to_case_invitation(
    db: AsyncSession, *, case_id: UUID, user_id: UUID, accept: bool
) -> CaseMember | None:
    result = await db.execute(
        select(CaseMember).where(
            CaseMember.case_id == case_id, CaseMember.user_id == user_id, CaseMember.status == "pending"
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        return None
    member.status = "accepted" if accept else "declined"
    await db.commit()
    await db.refresh(member)
    return member


async def remove_case_member(db: AsyncSession, *, case_id: UUID, user_id: UUID) -> bool:
    result = await db.execute(
        select(CaseMember).where(CaseMember.case_id == case_id, CaseMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if member is None:
        return False
    await db.delete(member)
    await db.commit()
    return True


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


async def link_vehicle_to_case(db: AsyncSession, *, case_id: UUID, vehicle_id: UUID) -> bool:
    case = await db.get(Case, case_id)
    vehicle = await db.get(Vehicle, vehicle_id)
    if case is None or vehicle is None:
        return False
    db.add(GraphEdge(
        source_type="vehicle", source_id=vehicle.id, target_type="case", target_id=case.id,
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

    appointments_result = await db.execute(
        select(Appointment).where(Appointment.case_id == case_id).order_by(Appointment.starts_at)
    )
    appointments = list(appointments_result.scalars().all())

    edges_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.target_type == "case", GraphEdge.target_id == case_id,
            GraphEdge.relationship_type == "belongs_to",
        )
    )
    edges = list(edges_result.scalars().all())
    task_ids = [edge.source_id for edge in edges if edge.source_type == "task"]
    decision_ids = [edge.source_id for edge in edges if edge.source_type == "decision"]
    vehicle_ids = [edge.source_id for edge in edges if edge.source_type == "vehicle"]

    tasks: list[Task] = []
    if task_ids:
        tasks_result = await db.execute(select(Task).where(Task.id.in_(task_ids)))
        tasks = list(tasks_result.scalars().all())

    decisions: list[Decision] = []
    if decision_ids:
        decisions_result = await db.execute(select(Decision).where(Decision.id.in_(decision_ids)))
        decisions = list(decisions_result.scalars().all())

    vehicles: list[Vehicle] = []
    if vehicle_ids:
        vehicles_result = await db.execute(select(Vehicle).where(Vehicle.id.in_(vehicle_ids)))
        vehicles = list(vehicles_result.scalars().all())

    return {
        "case": case,
        "documents": documents,
        "tasks": tasks,
        "decisions": decisions,
        "vehicles": vehicles,
        "appointments": appointments,
    }
