from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.db import async_session
from api.models import Document, User, UserFact
from api.user_facts import EXTRACTION_SCHEMA, detect_conflicts, extract_facts_from_document, get_current_facts

FAKE_EXTRACTION = (
    '{"facts": [{"fact_type": "address", "value": "Kerkstraat 1, Amsterdam", '
    '"valid_from": "2026-01-01", "valid_to": null, "confidence": 0.8}]}'
)


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_document(owner_id) -> Document:
    async with async_session() as db:
        document = Document(owner_id=owner_id, title="t", filename="f.pdf", mime_type="application/pdf")
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def _create_fact(
    user_id, *, fact_type: str = "address", value: str = "Kerkstraat 1, Amsterdam",
    valid_from: date = date(2020, 1, 1), valid_to: date | None = None, status: str = "confirmed",
) -> UserFact:
    async with async_session() as db:
        fact = UserFact(
            user_id=user_id, fact_type=fact_type, value={"text": value},
            valid_from=valid_from, valid_to=valid_to, status=status,
        )
        db.add(fact)
        await db.commit()
        await db.refresh(fact)
        return fact


async def test_extract_facts_requests_the_json_schema():
    user = await _create_user(_unique("factuser"))
    doc = await _create_document(user.id)
    with patch("api.user_facts.chat_completion", AsyncMock(return_value=FAKE_EXTRACTION)) as mock_completion:
        async with async_session() as db:
            facts = await extract_facts_from_document(
                db, document_id=doc.id, text="I moved to Kerkstraat 1 on Jan 1 2026.", user_id=user.id
            )

    assert mock_completion.call_args.kwargs["schema"] == EXTRACTION_SCHEMA
    assert len(facts) == 1
    assert facts[0].fact_type == "address"
    assert facts[0].value == {"text": "Kerkstraat 1, Amsterdam"}
    assert facts[0].valid_from == date(2026, 1, 1)
    assert facts[0].valid_to is None
    assert facts[0].status == "pending_review"


async def test_extract_facts_returns_empty_list_on_unparseable_output():
    user = await _create_user(_unique("factbaduser"))
    doc = await _create_document(user.id)
    with patch("api.user_facts.chat_completion", AsyncMock(return_value="not json")):
        async with async_session() as db:
            facts = await extract_facts_from_document(db, document_id=doc.id, text="x", user_id=user.id)

    assert facts == []


async def test_extract_facts_skips_facts_with_no_valid_from():
    user = await _create_user(_unique("factnodateuser"))
    doc = await _create_document(user.id)
    fake = '{"facts": [{"fact_type": "address", "value": "somewhere", "valid_from": null, "valid_to": null, "confidence": 0.5}]}'
    with patch("api.user_facts.chat_completion", AsyncMock(return_value=fake)):
        async with async_session() as db:
            facts = await extract_facts_from_document(db, document_id=doc.id, text="x", user_id=user.id)

    assert facts == []


async def test_detect_conflicts_finds_overlapping_open_ended_fact():
    user = await _create_user(_unique("conflictuser1"))
    doc = await _create_document(user.id)
    with patch("api.user_facts.chat_completion", AsyncMock(return_value=FAKE_EXTRACTION)):
        async with async_session() as db:
            await extract_facts_from_document(db, document_id=doc.id, text="x", user_id=user.id)

    async with async_session() as db:
        conflicts = await detect_conflicts(
            db, user_id=user.id, fact_type="address", valid_from=date(2026, 6, 1), valid_to=None,
        )
    assert len(conflicts) == 1


async def test_detect_conflicts_ignores_non_overlapping_period():
    user = await _create_user(_unique("conflictuser2"))
    doc = await _create_document(user.id)
    fake = (
        '{"facts": [{"fact_type": "address", "value": "old place", '
        '"valid_from": "2020-01-01", "valid_to": "2021-01-01", "confidence": 0.8}]}'
    )
    with patch("api.user_facts.chat_completion", AsyncMock(return_value=fake)):
        async with async_session() as db:
            await extract_facts_from_document(db, document_id=doc.id, text="x", user_id=user.id)

    async with async_session() as db:
        conflicts = await detect_conflicts(
            db, user_id=user.id, fact_type="address", valid_from=date(2026, 1, 1), valid_to=None,
        )
    assert conflicts == []


async def test_detect_conflicts_ignores_a_different_fact_type():
    user = await _create_user(_unique("conflictuser3"))
    doc = await _create_document(user.id)
    with patch("api.user_facts.chat_completion", AsyncMock(return_value=FAKE_EXTRACTION)):
        async with async_session() as db:
            await extract_facts_from_document(db, document_id=doc.id, text="x", user_id=user.id)

    async with async_session() as db:
        conflicts = await detect_conflicts(
            db, user_id=user.id, fact_type="employer", valid_from=date(2026, 1, 1), valid_to=None,
        )
    assert conflicts == []


async def test_detect_conflicts_excludes_given_id():
    user = await _create_user(_unique("conflictuser4"))
    doc = await _create_document(user.id)
    with patch("api.user_facts.chat_completion", AsyncMock(return_value=FAKE_EXTRACTION)):
        async with async_session() as db:
            facts = await extract_facts_from_document(db, document_id=doc.id, text="x", user_id=user.id)

    async with async_session() as db:
        conflicts = await detect_conflicts(
            db, user_id=user.id, fact_type="address", valid_from=date(2026, 6, 1), valid_to=None,
            exclude_id=facts[0].id,
        )
    assert conflicts == []



async def test_get_current_facts_returns_a_confirmed_fact_valid_today():
    user = await _create_user(_unique("currentfactuser1"))
    await _create_fact(user.id, status="confirmed")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert len(facts) == 1
    assert facts[0].fact_type == "address"


async def test_get_current_facts_excludes_pending_review_facts():
    user = await _create_user(_unique("currentfactuser2"))
    await _create_fact(user.id, status="pending_review")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert facts == []


async def test_get_current_facts_excludes_rejected_facts():
    user = await _create_user(_unique("currentfactuser3"))
    await _create_fact(user.id, status="rejected")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert facts == []


async def test_get_current_facts_excludes_a_fact_whose_valid_to_has_passed():
    user = await _create_user(_unique("currentfactuser4"))
    await _create_fact(user.id, valid_from=date(2020, 1, 1), valid_to=date(2021, 1, 1), status="confirmed")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert facts == []


async def test_get_current_facts_excludes_a_fact_not_yet_valid():
    user = await _create_user(_unique("currentfactuser5"))
    await _create_fact(user.id, valid_from=date(2099, 1, 1), valid_to=None, status="confirmed")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert facts == []


async def test_get_current_facts_includes_an_open_ended_fact_started_in_the_past():
    user = await _create_user(_unique("currentfactuser6"))
    await _create_fact(user.id, valid_from=date(2020, 1, 1), valid_to=None, status="confirmed")

    async with async_session() as db:
        facts = await get_current_facts(db, user_id=user.id)

    assert len(facts) == 1