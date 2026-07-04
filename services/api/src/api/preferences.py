"""Personal AI: durable, explicitly-set user preferences (Phase 13, ADR 0028).

Distinct from api.memory (Phase 8b), which stores facts extracted from
conversations -- these are set deliberately by the user themselves and
don't expire. One row per user, upserted.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import UserPreference


async def get_preferences(db: AsyncSession, *, user_id: UUID) -> UserPreference | None:
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    return result.scalar_one_or_none()


def build_language_instruction(preferred_language: str | None) -> str:
    """The shared wording used everywhere a preferred_language is injected
    into a system prompt (chat, manager agent, legal draft). Phrased as an
    explicit imperative ("you must ... regardless of ...") rather than a
    mild trailing note -- a small instruct model follows a direct directive
    more reliably than a soft aside, and this was previously only wired
    into /chat, so a user's preference silently had no effect on
    /manager/ask or Legal Draft at all."""
    if not preferred_language:
        return ""
    return (
        f" IMPORTANT: You must respond only in {preferred_language}, regardless of what "
        f"language the user's message or the provided context is written in."
    )


async def set_preferences(db: AsyncSession, *, user_id: UUID, preferred_language: str | None) -> UserPreference:
    preferences = await get_preferences(db, user_id=user_id)
    if preferences is None:
        preferences = UserPreference(user_id=user_id, preferred_language=preferred_language)
        db.add(preferences)
    else:
        preferences.preferred_language = preferred_language
    await db.commit()
    await db.refresh(preferences)
    return preferences


async def delete_preferences(db: AsyncSession, *, user_id: UUID) -> bool:
    preferences = await get_preferences(db, user_id=user_id)
    if preferences is None:
        return False
    await db.delete(preferences)
    await db.commit()
    return True
