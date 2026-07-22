"""Shareable-link tokens for Document/Case/Task detail views (Phase 29)."""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ShareLink

TOKEN_TTL_DAYS = 7


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


async def create_or_rotate_share_link(
    db: AsyncSession, *, entity_type: str, entity_id: UUID, created_by_user_id: UUID,
) -> ShareLink:
    existing = await db.execute(
        select(ShareLink).where(ShareLink.entity_type == entity_type, ShareLink.entity_id == entity_id)
    )
    link = existing.scalar_one_or_none()
    expires_at = datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS)
    if link is not None:
        link.token = _generate_token()
        link.created_by_user_id = created_by_user_id
        link.expires_at = expires_at
    else:
        link = ShareLink(
            entity_type=entity_type, entity_id=entity_id, token=_generate_token(),
            created_by_user_id=created_by_user_id, expires_at=expires_at,
        )
        db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def get_valid_share_link(db: AsyncSession, *, token: str) -> ShareLink | None:
    result = await db.execute(select(ShareLink).where(ShareLink.token == token))
    link = result.scalar_one_or_none()
    if link is None or link.expires_at < datetime.now(timezone.utc):
        return None
    return link
