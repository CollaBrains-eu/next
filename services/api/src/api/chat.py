"""AI Orchestrator: retrieval-augmented chat (ADR 0003).

Always retrieves via the Search Agent (api.search_service.hybrid_search),
then answers via the AI Gateway. No autonomous multi-step planning or
free-form tool routing yet -- that's the Planner Agent's job (Phase 2b).
No client-managed multi-turn history requirement either now that long-term
memory exists (Phase 8b, ADR 0018): callers can still pass prior turns via
`history` for same-session continuity, but relevant facts from *past*
conversations are retrieved automatically via `api.memory` and injected
alongside document context. After responding, a background task decides
whether this exchange is itself worth remembering.

After generating an answer, a Reflection step (ADR 0020) checks whether the
context actually supported it, retrying retrieval once with a wider net if
not. Reflection failures never affect the returned answer -- see
api.reflection and ADR 0020 for the "never fail the primary flow" reasoning.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.auth import get_effective_user
from api.db import async_session, get_db
from api.memory import maybe_create_memory_from_exchange, retrieve_relevant_memories
from api.models import Document, User
from api.reflection import log_reflection, reflect
from api.search_service import hybrid_search

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

REFLECTION_RETRY_CAP = 20

SYSTEM_PROMPT = (
    "You are the CollaBrains assistant. Answer the user's question using ONLY the "
    "provided context excerpts. If the context doesn't contain the answer, say so "
    "plainly instead of guessing. Cite sources by their [n] marker inline."
)


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = []


class Citation(BaseModel):
    marker: int
    document_id: UUID
    document_title: str
    chunk_id: UUID


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]


async def _retrieve(db: AsyncSession, query: str, limit: int) -> tuple[list[Citation], str]:
    hits = await hybrid_search(db, query, limit=limit)

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


async def _extract_and_store_memory(user_id: UUID, user_message: str, answer: str) -> None:
    try:
        async with async_session() as db:
            await maybe_create_memory_from_exchange(db, user_id=user_id, user_message=user_message, answer=answer)
    except Exception:  # noqa: BLE001 - background memory extraction must never surface as a request failure
        logger.exception("memory extraction failed for user %s", user_id)


def _build_messages(history: list[ChatTurn], context_text: str, question: str, memory_text: str = "") -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": turn.role, "content": turn.content} for turn in history)
    messages.append({"role": "user", "content": f"Context:\n{context_text}{memory_text}\n\nQuestion: {question}"})
    return messages


@router.post("/chat", response_model=ChatResponse)
async def chat(
    background_tasks: BackgroundTasks,
    request: ChatRequest,
    context_chunks: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> ChatResponse:
    citations, context_text = await _retrieve(db, request.message, context_chunks)

    try:
        memories = await retrieve_relevant_memories(db, user_id=current_user.id, query=request.message)
    except Exception:  # noqa: BLE001 - memory retrieval must never fail the chat response
        logger.exception("memory retrieval failed for chat request")
        memories = []

    memory_text = ""
    if memories:
        memory_lines = "\n".join(f"- {memory.summary}" for memory in memories)
        memory_text = f"\n\nRelevant memories:\n{memory_lines}"

    messages = _build_messages(request.history, context_text, request.message, memory_text)
    answer = await chat_completion(messages, user_id=current_user.id, endpoint="chat")

    try:
        result = await reflect(
            question=request.message, answer=answer, context_text=context_text,
            user_id=current_user.id, endpoint="chat",
        )
        retried = False
        if not result.sufficient_evidence and context_chunks < REFLECTION_RETRY_CAP:
            retry_limit = min(context_chunks * 2, REFLECTION_RETRY_CAP)
            citations, context_text = await _retrieve(db, request.message, retry_limit)
            messages = _build_messages(request.history, context_text, request.message, memory_text)
            answer = await chat_completion(messages, user_id=current_user.id, endpoint="chat")
            retried = True
        await log_reflection(
            db, user_id=current_user.id, endpoint="chat", question=request.message,
            result=result, retried=retried,
        )
    except Exception:  # noqa: BLE001 - reflection is a quality check, must never fail the chat response
        logger.exception("reflection failed for chat request from user %s", current_user.id)

    background_tasks.add_task(_extract_and_store_memory, current_user.id, request.message, answer)

    return ChatResponse(answer=answer, citations=citations)
