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
from api.models import Document

logger = logging.getLogger(__name__)

VALID_DOC_TYPES = {"invoice", "contract", "correspondence", "legal", "other"}

CLASSIFICATION_PROMPT = """Classify the following document. Return ONLY a JSON object \
(no prose, no markdown fences) with this shape:

{{"doc_type": "invoice"|"contract"|"correspondence"|"legal"|"other", \
"tags": [str, ...], "correspondent": str|null, "confidence": float}}

"tags" should be short, lowercase keywords (max 5). "correspondent" is the sender/counterparty \
name if identifiable, otherwise null. "confidence" is 0.0-1.0, your confidence in "doc_type".

Document:
{text}"""


class DocumentClassification(BaseModel):
    doc_type: str
    tags: list[str]
    correspondent: str | None
    confidence: float


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
    correspondent = payload.get("correspondent")
    correspondent = str(correspondent)[:255] if correspondent else None
    confidence = payload.get("confidence")
    confidence = float(confidence) if isinstance(confidence, (int, float)) and 0 <= confidence <= 1 else 0.0

    return DocumentClassification(doc_type=doc_type, tags=tags, correspondent=correspondent, confidence=confidence)


async def classify_document(*, text: str, user_id: UUID) -> DocumentClassification | None:
    """Classify `text` via the AI Gateway. Returns None on unparseable model output
    (graceful degradation, same as memory.py/entity_agent.py -- a bad classification
    call must never crash the document pipeline it's a subscriber of)."""
    prompt = CLASSIFICATION_PROMPT.format(text=text[:8000])
    raw = await chat_completion(
        [{"role": "user", "content": prompt}], user_id=user_id, endpoint="document.classify", json_mode=True
    )
    return _parse_classification(raw)


async def classify_and_persist(db: AsyncSession, *, document_id: UUID, text: str, user_id: UUID) -> Document | None:
    document = await db.get(Document, document_id)
    if document is None:
        return None

    result = await classify_document(text=text, user_id=user_id)
    if result is None:
        return document

    document.doc_type = result.doc_type
    document.tags = result.tags
    document.correspondent = result.correspondent
    document.classification_confidence = result.confidence
    await db.commit()
    await db.refresh(document)
    return document
