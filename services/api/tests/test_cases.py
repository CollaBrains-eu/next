from uuid import uuid4

from api.db import async_session
from api.models import Case, Document, User


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def test_case_can_be_created_and_defaults_to_open_status():
    user = await _create_user(_unique("caseuser"))

    async with async_session() as db:
        case = Case(user_id=user.id, name="Smith v. Jones")
        db.add(case)
        await db.commit()
        await db.refresh(case)

    assert case.status == "open"
    assert case.description is None


async def test_document_case_id_defaults_to_none():
    user = await _create_user(_unique("caseuser"))

    async with async_session() as db:
        document = Document(
            owner_id=user.id, title="t", filename="t.pdf", mime_type="application/pdf", status="ready",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

    assert document.case_id is None
