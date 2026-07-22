"""Audit-log service for Document/Case/Task lifecycle events (Phase 29)."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ActivityLogEntry


async def log_activity(
    db: AsyncSession, *, entity_type: str, entity_id: UUID, action: str,
    actor_user_id: UUID, detail: dict | None = None,
) -> ActivityLogEntry:
    """Commits internally, like AiCallLog's write. Only call this either (a)
    after the primary mutation's own commit has already landed, or (b) for
    deletes, immediately before deleting the row, having already copied any
    display fields (title/name) into `detail`."""
    entry = ActivityLogEntry(
        entity_type=entity_type, entity_id=entity_id, action=action,
        actor_user_id=actor_user_id, detail=detail or {},
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_activity(
    db: AsyncSession, *, entity_type: str, entity_id: UUID, limit: int = 50, offset: int = 0,
) -> list[ActivityLogEntry]:
    result = await db.execute(
        select(ActivityLogEntry)
        .where(ActivityLogEntry.entity_type == entity_type, ActivityLogEntry.entity_id == entity_id)
        .order_by(ActivityLogEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
