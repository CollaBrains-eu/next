"""Legal Agent: grounded drafting from ingested documents (ADR 0004).

Deliberately NOT a general legal-reasoning chatbot -- see the ADR. Every
response is a draft requiring attorney review, grounded only in retrieved
document context, never the model's own "knowledge" of law.

`_generate_draft` is a plain function, not inlined in the endpoint, so the
Planning Engine (Phase 8c, ADR 0019) can call the same code the HTTP
endpoint does for the "Draft legal document"/"Prepare objection" goals.
Reflection (Phase 8d, ADR 0020) lives inside `_generate_draft` itself for
the same reason: wiring it into the shared function, not just the HTTP
handler, means plan-initiated drafts get the same hallucination check as
direct API calls, with no extra code at either call site. After drafting,
Reflection checks whether the context actually supported it and retries
retrieval once with a wider net if not; reflection failures never affect
the returned draft -- see api.reflection and ADR 0020.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.auth import get_current_user
from api.db import get_db
from api.models import Document, User
from api.preferences import build_language_instruction, get_preferences
from api.reflection import log_reflection, reflect
from api.search_service import hybrid_search
from api.text_language import ts_config_for_preferred_language
from api.user_facts import get_current_facts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/legal", tags=["legal"])

REFLECTION_RETRY_CAP = 20

DISCLAIMER = (
    "This is an AI-generated draft grounded only in the documents provided to it. "
    "It is not legal advice and has not been reviewed by an attorney. Verify every "
    "factual and legal claim before use."
)

SYSTEM_PROMPT = (
    "You are a legal drafting assistant. Draft the requested document using ONLY the "
    "provided context excerpts as your factual and legal basis. Never cite case law, "
    "statutes, or facts that are not present in the context. If the context is "
    "insufficient to complete the request, say so explicitly instead of filling gaps "
    "with assumptions. Cite context sources by their [n] marker inline. This is always "
    "a draft for attorney review, never a final filing."
)


class DraftRequest(BaseModel):
    instruction: str
    document_ids: list[UUID] = []
    context_chunks: int = 8


class Citation(BaseModel):
    marker: int
    document_id: UUID
    document_title: str
    chunk_id: UUID


class DraftResponse(BaseModel):
    draft: str
    citations: list[Citation]
    disclaimer: str = DISCLAIMER


async def _retrieve(
    db: AsyncSession, instruction: str, limit: int, scope: set[UUID] | None, owner_id: UUID,
    language: str = "english",
) -> tuple[list[Citation], str]:
    hits = await hybrid_search(db, instruction, limit=limit, owner_id=owner_id, document_ids=scope, language=language)

    citations: list[Citation] = []
    context_blocks: list[str] = []
    if hits:
        hit_document_ids = {hit.chunk.document_id for hit in hits}
        documents_result = await db.execute(select(Document).where(Document.id.in_(hit_document_ids)))
        titles = {doc.id: doc.title for doc in documents_result.scalars().all()}

        for marker, hit in enumerate(hits, start=1):
            citations.append(
                Citation(
                    marker=marker,
                    document_id=hit.chunk.document_id,
                    document_title=titles.get(hit.chunk.document_id, ""),
                    chunk_id=hit.chunk.id,
                )
            )
            context_blocks.append(f"[{marker}] {hit.chunk.content}")

    context_text = "\n\n".join(context_blocks) if context_blocks else "(no relevant documents found)"
    return citations, context_text


async def _generate_draft(
    db: AsyncSession, *, instruction: str, user_id: UUID, document_ids: list[UUID] | None = None,
    context_chunks: int = 8,
) -> DraftResponse:
    scope = set(document_ids) if document_ids else None

    preferred_language: str | None = None
    try:
        preferences = await get_preferences(db, user_id=user_id)
        preferred_language = preferences.preferred_language if preferences else None
    except Exception:  # noqa: BLE001 - preference lookup must never fail the draft response
        logger.exception("preference lookup failed for legal draft request")
    search_language = ts_config_for_preferred_language(preferred_language)
    language_instruction = build_language_instruction(preferred_language)

    citations, context_text = await _retrieve(db, instruction, context_chunks, scope, user_id, search_language)

    try:
        facts = await get_current_facts(db, user_id=user_id)
    except Exception:  # noqa: BLE001 - facts retrieval must never fail the draft response
        logger.exception("facts retrieval failed for legal draft request")
        facts = []

    facts_text = ""
    if facts:
        fact_lines = "\n".join(f"- {fact.fact_type}: {fact.value.get('text', '')}" for fact in facts)
        facts_text = f"\n\nKnown facts about the user:\n{fact_lines}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + language_instruction},
        {"role": "user", "content": f"Context:\n{context_text}{facts_text}\n\nDrafting instruction: {instruction}"},
    ]
    draft_text = await chat_completion(messages, user_id=user_id, endpoint="legal.draft")

    try:
        result = await reflect(
            question=instruction, answer=draft_text, context_text=context_text,
            user_id=user_id, endpoint="legal.draft",
        )
        retried = False
        if not result.sufficient_evidence and context_chunks < REFLECTION_RETRY_CAP:
            retry_limit = min(context_chunks * 2, REFLECTION_RETRY_CAP)
            citations, context_text = await _retrieve(db, instruction, retry_limit, scope, user_id, search_language)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT + language_instruction},
                {"role": "user", "content": f"Context:\n{context_text}{facts_text}\n\nDrafting instruction: {instruction}"},
            ]
            draft_text = await chat_completion(messages, user_id=user_id, endpoint="legal.draft")
            retried = True
        await log_reflection(
            db, user_id=user_id, endpoint="legal.draft", question=instruction,
            result=result, retried=retried,
        )
    except Exception:  # noqa: BLE001 - reflection is a quality check, must never fail the draft response
        logger.exception("reflection failed for legal draft request from user %s", user_id)

    return DraftResponse(draft=draft_text, citations=citations)


@router.post("/draft", response_model=DraftResponse)
async def draft(
    request: DraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftResponse:
    return await _generate_draft(
        db,
        instruction=request.instruction,
        user_id=current_user.id,
        document_ids=request.document_ids,
        context_chunks=request.context_chunks,
    )
