"""Document classification: doc-type/tags/correspondent extraction (Phase 23).

Migrated from CollaBrains v2's paperless-gpt integration (7 separate prompts:
title/correspondent/document_type/tag/created_date/custom_field/OCR), but not
its architecture -- v2's own v3 redesign already abandoned that in favor of
one consolidated prompt (see docs/superpowers/plans/2026-07-09-fase1-admin-dashboard.md
§3.2). This module follows the same single json_mode-call pattern as
entity_agent.py/planner_agent.py instead.
"""
import json
import logging
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.document_categories import DOC_TYPE_TO_CATEGORY_SLUG, VALID_DOC_TYPES
from api.models import Document

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """Classify the following document. Return ONLY a JSON object \
(no prose, no markdown fences) with this shape:

{{"doc_type": one of {doc_types}, "tags": [str, ...], "confidence": float, \
"correspondent": {{"name": str|null, "street": str|null, "house_number": str|null, \
"po_box": str|null, "postal_code": str|null, "city": str|null, "country": str|null}}}}

"tags" should be short, lowercase keywords (max 5). "confidence" is 0.0-1.0, your confidence \
in "doc_type". "correspondent" is the sender/counterparty -- fill in whichever address fields \
are identifiable in the document (e.g. a letterhead or footer) and null the rest; if no \
correspondent is identifiable at all, return all of its fields as null.

Document:
{text}"""

CORRESPONDENT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": ["string", "null"]},
        "street": {"type": ["string", "null"]},
        "house_number": {"type": ["string", "null"]},
        "po_box": {"type": ["string", "null"]},
        "postal_code": {"type": ["string", "null"]},
        "city": {"type": ["string", "null"]},
        "country": {"type": ["string", "null"]},
    },
    "required": ["name", "street", "house_number", "po_box", "postal_code", "city", "country"],
}

CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string", "enum": sorted(VALID_DOC_TYPES)},
        "tags": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "correspondent": CORRESPONDENT_SCHEMA,
    },
    "required": ["doc_type", "tags", "confidence", "correspondent"],
}


class CorrespondentAddress(BaseModel):
    name: str | None
    street: str | None
    house_number: str | None
    po_box: str | None
    postal_code: str | None
    city: str | None
    country: str | None


class DocumentClassification(BaseModel):
    doc_type: str
    tags: list[str]
    confidence: float
    correspondent: CorrespondentAddress


def _clean_str(value: object, max_len: int) -> str | None:
    return str(value)[:max_len] if value else None


def _parse_correspondent(payload: object) -> CorrespondentAddress:
    if not isinstance(payload, dict):
        payload = {}
    return CorrespondentAddress(
        name=_clean_str(payload.get("name"), 255),
        street=_clean_str(payload.get("street"), 255),
        house_number=_clean_str(payload.get("house_number"), 20),
        po_box=_clean_str(payload.get("po_box"), 20),
        postal_code=_clean_str(payload.get("postal_code"), 20),
        city=_clean_str(payload.get("city"), 255),
        country=_clean_str(payload.get("country"), 100),
    )


def _parse_classification(raw: str) -> DocumentClassification | None:
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
    except (json.JSONDecodeError, ValueError):
        logger.warning("document_classification: could not parse output: %r", raw[:500])
        return None

    doc_type = payload.get("doc_type") if payload.get("doc_type") in VALID_DOC_TYPES else "other"
    tags = payload.get("tags")
    tags = [str(t)[:100] for t in tags][:5] if isinstance(tags, list) else []
    confidence = payload.get("confidence")
    confidence = float(confidence) if isinstance(confidence, (int, float)) and 0 <= confidence <= 1 else 0.0
    correspondent = _parse_correspondent(payload.get("correspondent"))

    return DocumentClassification(doc_type=doc_type, tags=tags, confidence=confidence, correspondent=correspondent)


async def classify_document(*, text: str, user_id: UUID) -> DocumentClassification | None:
    """Classify `text` via the AI Gateway. Returns None on unparseable model output
    (graceful degradation, same as memory.py/entity_agent.py -- a bad classification
    call must never crash the document pipeline it's a subscriber of)."""
    prompt = CLASSIFICATION_PROMPT.format(
        doc_types=" | ".join(f'"{t}"' for t in sorted(VALID_DOC_TYPES)), text=text[:8000],
    )
    raw = await chat_completion(
        [{"role": "user", "content": prompt}],
        user_id=user_id,
        endpoint="document.classify",
        schema=CLASSIFICATION_SCHEMA,
    )
    return _parse_classification(raw)


async def _category_id_for_doc_type(db: AsyncSession, doc_type: str) -> UUID | None:
    from sqlalchemy import select

    from api.models import Category

    slug = DOC_TYPE_TO_CATEGORY_SLUG.get(doc_type, "other_documents")
    category = (
        await db.execute(select(Category).where(Category.slug == slug, Category.category_type == "document"))
    ).scalar_one_or_none()
    return category.id if category is not None else None


async def classify_and_persist(db: AsyncSession, *, document_id: UUID, text: str, user_id: UUID) -> Document | None:
    document = await db.get(Document, document_id)
    if document is None:
        return None

    result = await classify_document(text=text, user_id=user_id)
    if result is None:
        return document

    document.doc_type = result.doc_type
    document.tags = result.tags
    document.correspondent = result.correspondent.name
    document.correspondent_street = result.correspondent.street
    document.correspondent_house_number = result.correspondent.house_number
    document.correspondent_po_box = result.correspondent.po_box
    document.correspondent_postal_code = result.correspondent.postal_code
    document.correspondent_city = result.correspondent.city
    document.correspondent_country = result.correspondent.country
    document.classification_confidence = result.confidence
    document.category_id = await _category_id_for_doc_type(db, result.doc_type)
    await db.commit()
    await db.refresh(document)
    return document
