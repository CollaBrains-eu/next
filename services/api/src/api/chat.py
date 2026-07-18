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

A verified-sufficient answer also reinforces the memories that
contributed to it (Phase 12, ADR 0027) -- the "learn" step of the
observe/plan/execute/verify/learn cycle, closing the one part of that
cycle that didn't already exist somewhere in this codebase.

If the user has set a preferred_language (Phase 13, ADR 0028), it's
appended to the system prompt on every request without needing to be
restated -- the one Personal AI integration point this phase adds.
"""
import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.auth import get_effective_user
from api.db import async_session, get_db
from api.memory import maybe_create_memory_from_exchange, reinforce_memories, retrieve_relevant_memories
from api.models import Document, User
from api.preferences import build_language_instruction, get_preferences
from api.reflection import log_reflection, reflect
from api.search_service import hybrid_search
from api.user_facts import get_current_facts

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

REFLECTION_RETRY_CAP = 20

# The event loop only holds a *weak* reference to asyncio.Task objects (see
# asyncio docs, "Task Object"). If nothing else holds a strong reference, a
# fire-and-forget task can be garbage-collected mid-flight, silently dropping
# whatever it was doing. This module-level set + done-callback is the pattern
# the docs themselves recommend for background tasks like memory extraction.
_background_tasks: set[asyncio.Task] = set()


def _spawn_background_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


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


class GroundedAnswer(BaseModel):
    answer: str
    citations: list[Citation]


async def _retrieve(db: AsyncSession, query: str, limit: int, owner_id: UUID) -> tuple[list[Citation], str]:
    hits = await hybrid_search(db, query, limit=limit, owner_id=owner_id)

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


def _build_messages(
    history: list[ChatTurn], context_text: str, question: str, memory_text: str = "",
    language_instruction: str = "", facts_text: str = "",
) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT + language_instruction}]
    messages.extend({"role": turn.role, "content": turn.content} for turn in history)
    messages.append({"role": "user", "content": f"Context:\n{context_text}{facts_text}{memory_text}\n\nQuestion: {question}"})
    return messages


async def answer_grounded_question(
    db: AsyncSession, *, user_id: UUID, message: str,
    history: list[ChatTurn] | None = None, context_chunks: int = 5,
) -> GroundedAnswer:
    """The full /chat pipeline (retrieve, memory, generate, Reflection, retry,
    background memory extraction) as a reusable function -- both the /chat
    route and api.tools' answer_from_documents tool call this, so document
    Q&A keeps Reflection and long-term memory no matter which caller reaches it.

    Runs outside a request lifecycle for tool-handler callers (no
    BackgroundTasks available), so the background memory-extraction step
    uses _spawn_background_task (asyncio.create_task plus a strong
    reference held until completion) instead -- same fire-and-forget
    semantics as the route's background_tasks.add_task call, without the
    risk of the task being garbage-collected mid-flight.
    """
    history = history or []
    citations, context_text = await _retrieve(db, message, context_chunks, user_id)

    try:
        memories = await retrieve_relevant_memories(db, user_id=user_id, query=message)
    except Exception:  # noqa: BLE001 - memory retrieval must never fail the answer
        logger.exception("memory retrieval failed for grounded question")
        memories = []

    memory_text = ""
    if memories:
        memory_lines = "\n".join(f"- {memory.summary}" for memory in memories)
        memory_text = f"\n\nRelevant memories:\n{memory_lines}"

    try:
        facts = await get_current_facts(db, user_id=user_id)
    except Exception:  # noqa: BLE001 - facts retrieval must never fail the answer
        logger.exception("facts retrieval failed for grounded question")
        facts = []

    facts_text = ""
    if facts:
        fact_lines = "\n".join(f"- {fact.fact_type}: {fact.value.get('text', '')}" for fact in facts)
        facts_text = f"\n\nKnown facts about the user:\n{fact_lines}"

    language_instruction = ""
    try:
        preferences = await get_preferences(db, user_id=user_id)
        language_instruction = build_language_instruction(preferences.preferred_language if preferences else None)
    except Exception:  # noqa: BLE001 - preference lookup must never fail the answer
        logger.exception("preference lookup failed for grounded question")

    messages = _build_messages(history, context_text, message, memory_text, language_instruction, facts_text)
    answer = await chat_completion(messages, user_id=user_id, endpoint="chat")

    try:
        result = await reflect(question=message, answer=answer, context_text=context_text, user_id=user_id, endpoint="chat")
        retried = False
        if not result.sufficient_evidence and context_chunks < REFLECTION_RETRY_CAP:
            retry_limit = min(context_chunks * 2, REFLECTION_RETRY_CAP)
            citations, context_text = await _retrieve(db, message, retry_limit, user_id)
            messages = _build_messages(history, context_text, message, memory_text, language_instruction, facts_text)
            answer = await chat_completion(messages, user_id=user_id, endpoint="chat")
            retried = True
        await log_reflection(db, user_id=user_id, endpoint="chat", question=message, result=result, retried=retried)
        if result.sufficient_evidence and memories:
            await reinforce_memories(db, [memory.id for memory in memories])
    except Exception:  # noqa: BLE001 - reflection is a quality check, must never fail the answer
        logger.exception("reflection failed for grounded question from user %s", user_id)

    _spawn_background_task(_extract_and_store_memory(user_id, message, answer))

    return GroundedAnswer(answer=answer, citations=citations)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    context_chunks: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> ChatResponse:
    result = await answer_grounded_question(
        db, user_id=current_user.id, message=request.message,
        history=request.history, context_chunks=context_chunks,
    )
    return ChatResponse(answer=result.answer, citations=result.citations)
