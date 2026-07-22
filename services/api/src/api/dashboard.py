"""Dashboard aggregation queries (sub-project 2 of the app-shell redesign).

The Activity Timeline merges recent items across four resource types, each
scoped by that resource's own existing visibility rule -- not a new,
parallel authorization scheme. Every WHERE clause below mirrors the exact
predicate the corresponding list endpoint already uses (see the comment on
each block), verified by reading those functions directly rather than
assumed.
"""
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Case, CaseMember, Document, Entity, Task


class ActivityItem:
    def __init__(self, *, type: str, id: UUID, title: str, created_at, link: str) -> None:
        self.type = type
        self.id = id
        self.title = title
        self.created_at = created_at
        self.link = link


async def get_user_activity(db: AsyncSession, *, user_id: UUID, limit: int = 15) -> list[ActivityItem]:
    # Documents: same scoping as documents.py's list_documents (non-admin branch).
    documents = list(
        (
            await db.execute(
                select(Document).where(Document.owner_id == user_id).order_by(Document.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )

    # Tasks: same scoping as tasks.py's list_tasks (non-admin branch) --
    # created_by == user, OR the task's document is owned by the user, OR
    # the task's document belongs to a case the user has *accepted*
    # membership on.
    member_exists = exists(
        select(CaseMember.id).where(
            CaseMember.case_id == Document.case_id,
            CaseMember.user_id == user_id,
            CaseMember.status == "accepted",
        )
    )
    tasks = list(
        (
            await db.execute(
                select(Task)
                .outerjoin(Document, Task.document_id == Document.id)
                .where(or_(Task.created_by == user_id, Document.owner_id == user_id, member_exists))
                .order_by(Task.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    # Cases: same scoping as cases.py's list_cases -- owned, or *accepted* member.
    cases = list(
        (
            await db.execute(
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
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    # Entities: same owner scoping as entities.py's list_entities, but
    # deliberately NOT filtered to status="confirmed" -- a newly-extracted
    # pending_review entity is legitimately recent activity here.
    entities = list(
        (
            await db.execute(
                select(Entity).where(Entity.owner_id == user_id).order_by(Entity.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )

    items = (
        [
            ActivityItem(type="document", id=d.id, title=d.title, created_at=d.created_at, link=f"/documents/{d.id}")
            for d in documents
        ]
        + [
            ActivityItem(
                type="task",
                id=t.id,
                title=t.title,
                created_at=t.created_at,
                link=f"/documents/{t.document_id}" if t.document_id else "/tasks",
            )
            for t in tasks
        ]
        + [ActivityItem(type="case", id=c.id, title=c.name, created_at=c.created_at, link=f"/cases/{c.id}") for c in cases]
        + [
            ActivityItem(type="entity", id=e.id, title=e.name, created_at=e.created_at, link=f"/entities/{e.id}")
            for e in entities
        ]
    )
    items.sort(key=lambda item: item.created_at, reverse=True)
    return items[:limit]
