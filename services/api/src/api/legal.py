"""Legal Agent: grounded drafting from ingested documents (ADR 0004).

Deliberately NOT a general legal-reasoning chatbot -- see the ADR. Every
response is a draft requiring attorney review, grounded only in retrieved
document context, never the model's own "knowledge" of law.

After drafting, a Reflection step (ADR 0020) checks whether the context
actually supported the draft, retrying retrieval once with a wider net if
not -- the same hallucination-risk check applied to /chat, wired in here
too since drafting is the higher-stakes of the two. Reflection failures
never affect the returned draft; see api.reflection and ADR 0020.
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
from api.reflection import log_reflection, reflect
from api.search_service import hybrid_search

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
    db: AsyncSession, instruction: str, limit: int, scope: set[UUID] | None
) -> tuple[list[Citation], str]:
    hits = await hybrid_search(db, instruction, limit=limit, document_ids=scope)

    citations: list[Citation] = []
    context_blocks: list[str] = []
    if hits:
        document_ids = {hit.chunk.document_id for hit in hits}
        documents_result = await db.execute(select(Document).where(Document.id.in_(document_ids)))
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


@router.post("/draft", response_model=DraftResponse)
async def draft(
    request: DraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftResponse:
    scope = set(request.document_ids) or None
    citations, context_text = await _retrieve(db, request.instruction, request.context_chunks, scope)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context_text}\n\nDrafting instruction: {request.instruction}"},
    ]
    draft_text = await chat_completion(messages, user_id=current_user.id, endpoint="legal.draft")

    try:
        result = await reflect(
            question=request.instruction, answer=draft_text, context_text=context_text,
            user_id=current_user.id, endpoint="legal.draft",
        )
        retried = False
        if not result.sufficient_evidence and request.context_chunks < REFLECTION_RETRY_CAP:
            retry_limit = min(request.context_chunks * 2, REFLECTION_RETRY_CAP)
            citations, context_text = await _retrieve(db, request.instruction, retry_limit, scope)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{context_text}\n\nDrafting instruction: {request.instruction}"},
            ]
            draft_text = await chat_completion(messages, user_id=current_user.id, endpoint="legal.draft")
            retried = True
        await log_reflection(
            db, user_id=current_user.id, endpoint="legal.draft", question=request.instruction,
            result=result, retried=retried,
        )
    except Exception:  # noqa: BLE001 - reflection is a quality check, must never fail the draft response
        logger.exception("reflection failed for legal draft request from user %s", current_user.id)

    return DraftResponse(draft=draft_text, citations=citations)
