"""AI Orchestrator: retrieval-augmented chat (ADR 0003).

Always retrieves via the Search Agent (api.search_service.hybrid_search),
then answers via the AI Gateway. No autonomous multi-step planning or
free-form tool routing yet -- that's the Planner Agent's job (Phase 2b).
No server-side conversation memory yet either: callers pass prior turns
themselves if they want multi-turn context.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.auth import get_current_user
from api.db import get_db
from api.models import Document, User
from api.search_service import hybrid_search

router = APIRouter(tags=["chat"])

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


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    context_chunks: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    hits = await hybrid_search(db, request.message, limit=context_chunks)

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

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": turn.role, "content": turn.content} for turn in request.history)
    messages.append({"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {request.message}"})

    answer = await chat_completion(messages, user_id=current_user.id, endpoint="chat")

    return ChatResponse(answer=answer, citations=citations)
