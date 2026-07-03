from uuid import uuid4

from api.db import async_session
from api.models import User
from api.preferences import delete_preferences, get_preferences, set_preferences


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def test_get_preferences_returns_none_when_unset():
    user = await _create_user(_unique("prefuser"))
    async with async_session() as db:
        preferences = await get_preferences(db, user_id=user.id)
    assert preferences is None


async def test_set_preferences_creates_a_new_row():
    user = await _create_user(_unique("prefuser"))
    async with async_session() as db:
        preferences = await set_preferences(db, user_id=user.id, preferred_language="de")
    assert preferences.preferred_language == "de"

    async with async_session() as db:
        fetched = await get_preferences(db, user_id=user.id)
    assert fetched.preferred_language == "de"


async def test_set_preferences_upserts_an_existing_row():
    user = await _create_user(_unique("prefuser"))
    async with async_session() as db:
        await set_preferences(db, user_id=user.id, preferred_language="de")
    async with async_session() as db:
        updated = await set_preferences(db, user_id=user.id, preferred_language="nl")
    assert updated.preferred_language == "nl"

    async with async_session() as db:
        fetched = await get_preferences(db, user_id=user.id)
    assert fetched.preferred_language == "nl"


async def test_delete_preferences_removes_the_row():
    user = await _create_user(_unique("prefuser"))
    async with async_session() as db:
        await set_preferences(db, user_id=user.id, preferred_language="de")

    async with async_session() as db:
        deleted = await delete_preferences(db, user_id=user.id)
    assert deleted is True

    async with async_session() as db:
        fetched = await get_preferences(db, user_id=user.id)
    assert fetched is None


async def test_delete_preferences_returns_false_when_nothing_to_delete():
    user = await _create_user(_unique("prefuser"))
    async with async_session() as db:
        deleted = await delete_preferences(db, user_id=user.id)
    assert deleted is False
