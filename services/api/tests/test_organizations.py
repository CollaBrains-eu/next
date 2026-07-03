from uuid import uuid4

import pytest

from api.db import async_session
from api.models import DEFAULT_ORGANIZATION_ID, User
from api.organizations import get_approval_required_goals, get_organization_for_user, set_organization_policies


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def test_new_users_default_to_the_default_organization():
    user = await _create_user(_unique("orguser"))
    assert user.organization_id == DEFAULT_ORGANIZATION_ID


async def test_get_organization_for_user_returns_the_default_organization():
    user = await _create_user(_unique("orguser"))
    async with async_session() as db:
        organization = await get_organization_for_user(db, user.id)
    assert organization is not None
    assert organization.id == DEFAULT_ORGANIZATION_ID


async def test_get_organization_for_user_returns_none_for_unknown_user():
    async with async_session() as db:
        organization = await get_organization_for_user(db, uuid4())
    assert organization is None


async def test_get_approval_required_goals_returns_default_when_no_override():
    user = await _create_user(_unique("orguser"))
    default = frozenset({"draft_legal_document", "prepare_objection"})

    async with async_session() as db:
        result = await get_approval_required_goals(db, user.id, default=default)

    assert result == default


async def test_get_approval_required_goals_returns_org_override_when_set():
    user = await _create_user(_unique("orguser"))
    default = frozenset({"draft_legal_document"})

    async with async_session() as db:
        await set_organization_policies(
            db, organization_id=DEFAULT_ORGANIZATION_ID,
            policies={"approval_required_goals": ["summarize_case"]},
        )
        result = await get_approval_required_goals(db, user.id, default=default)

    assert result == frozenset({"summarize_case"})

    # restore, since organizations table is shared across tests in this run
    async with async_session() as db:
        await set_organization_policies(db, organization_id=DEFAULT_ORGANIZATION_ID, policies={})


async def test_get_approval_required_goals_ignores_a_malformed_override():
    user = await _create_user(_unique("orguser"))
    default = frozenset({"draft_legal_document"})

    async with async_session() as db:
        await set_organization_policies(
            db, organization_id=DEFAULT_ORGANIZATION_ID, policies={"approval_required_goals": "not-a-list"},
        )
        result = await get_approval_required_goals(db, user.id, default=default)

    assert result == default

    async with async_session() as db:
        await set_organization_policies(db, organization_id=DEFAULT_ORGANIZATION_ID, policies={})


async def test_set_organization_policies_rejects_unknown_organization():
    async with async_session() as db:
        with pytest.raises(ValueError):
            await set_organization_policies(db, organization_id=uuid4(), policies={})
