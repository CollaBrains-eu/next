"""User Facts: temporal fact memory (Phase 26).

Neither CollaBrains v2 (a flat key-value `UserKnowledge` table, no
validity periods) nor Next's existing `memories` table (episodic
conversation facts, no "what is true right now" semantics) tracked
time-bound facts like "address X valid from date A to date B". The
unbuilt v2-successor design (`v3/backend/app/models/fact.py`) sketched
this shape; this module implements it against Next's own conventions
(json_mode extraction like entity_agent.py, `pending_review` status like
Entity (ADR 0008/Phase 21) instead of a separate review-queue system).
"""
import json
import logging
from datetime import date
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.models import UserFact

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract time-bound facts about a person from the following document -- \
facts like address, employer, marital status, or similar durable attributes that can change \
over time. Return ONLY a JSON object (no prose, no markdown fences) with this shape:

{{"facts": [{{"fact_type": str, "value": str, "valid_from": "YYYY-MM-DD"|null, \
"valid_to": "YYYY-MM-DD"|null, "confidence": float}}]}}

Only extract facts with an explicit or clearly inferable date. If there are no such facts, \
return {{"facts": []}}.

Document:
{text}"""

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact_type": {"type": "string"},
                    "value": {"type": "string"},
                    "valid_from": {"type": ["string", "null"]},
                    "valid_to": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                },
                "required": ["fact_type", "value"],
            },
        },
    },
    "required": ["facts"],
}


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def detect_conflicts(
    db: AsyncSession, *, user_id: UUID, fact_type: str, valid_from: date, valid_to: date | None,
    exclude_id: UUID | None = None,
) -> list[UserFact]:
    """Find existing facts of the same (user_id, fact_type) whose validity period overlaps
    [valid_from, valid_to). An open-ended valid_to (None) is treated as "still valid"."""
    conditions = [
        UserFact.user_id == user_id,
        UserFact.fact_type == fact_type,
        UserFact.status != "rejected",
        or_(UserFact.valid_to.is_(None), UserFact.valid_to >= valid_from),
    ]
    if valid_to is not None:
        conditions.append(UserFact.valid_from <= valid_to)
    if exclude_id is not None:
        conditions.append(UserFact.id != exclude_id)

    result = await db.execute(select(UserFact).where(and_(*conditions)))
    return list(result.scalars().all())


async def get_current_facts(db: AsyncSession, *, user_id: UUID) -> list[UserFact]:
    """Confirmed facts valid right now (Phase 26 read path -- extraction
    and review already existed; nothing consumed the result until this).
    Only status == "confirmed": a pending_review fact could be a bad
    extraction, which is exactly what the review step exists to catch."""
    today = date.today()
    result = await db.execute(
        select(UserFact)
        .where(
            UserFact.user_id == user_id,
            UserFact.status == "confirmed",
            UserFact.valid_from <= today,
            or_(UserFact.valid_to.is_(None), UserFact.valid_to >= today),
        )
        .order_by(UserFact.fact_type)
    )
    return list(result.scalars().all())


async def extract_facts_from_document(
    db: AsyncSession, *, document_id: UUID, text: str, user_id: UUID,
) -> list[UserFact]:
    prompt = EXTRACTION_PROMPT.format(text=text[:8000])
    raw = await chat_completion(
        [{"role": "user", "content": prompt}], user_id=user_id, endpoint="facts.extract", schema=EXTRACTION_SCHEMA
    )

    try:
        payload = json.loads(raw)
        raw_facts = payload.get("facts", [])
        if not isinstance(raw_facts, list):
            raise ValueError("facts must be an array")
    except (json.JSONDecodeError, ValueError, AttributeError):
        logger.warning("user_facts: could not parse extraction output: %r", raw[:500])
        return []

    persisted: list[UserFact] = []
    for item in raw_facts:
        if not isinstance(item, dict) or not item.get("fact_type") or not item.get("value"):
            continue
        valid_from = _parse_date(item.get("valid_from"))
        if valid_from is None:
            continue  # a fact with no determinable start date isn't useful for point-in-time queries
        valid_to = _parse_date(item.get("valid_to"))
        confidence = item.get("confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) and 0 <= confidence <= 1 else 0.0

        fact = UserFact(
            user_id=user_id,
            fact_type=str(item["fact_type"])[:100],
            value={"text": str(item["value"])[:2000]},
            valid_from=valid_from,
            valid_to=valid_to,
            confidence=confidence,
            source_document_id=document_id,
        )
        db.add(fact)
        persisted.append(fact)

    await db.commit()
    for fact in persisted:
        await db.refresh(fact)
    return persisted
