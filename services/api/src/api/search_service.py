"""Hybrid (keyword + semantic) search over document chunks.

This is the "Search Agent" from ADR 0003 — a single reusable function
rather than a distinct agent abstraction, since it has a handful of
callers (the /search endpoint, the chat orchestrator's retrieval step,
and the Legal Agent's context-gathering step).
"""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.embeddings import embed_text
from api.models import DocumentChunk


@dataclass
class SearchHit:
    chunk: DocumentChunk
    score: float


async def hybrid_search(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    *,
    document_ids: set[UUID] | None = None,
) -> list[SearchHit]:
    candidate_pool = max(limit * 3, 20)
    rrf_k = 60

    query_vector = await embed_text(query)
    semantic_query = select(DocumentChunk).order_by(DocumentChunk.embedding.cosine_distance(query_vector))
    if document_ids:
        semantic_query = semantic_query.where(DocumentChunk.document_id.in_(document_ids))
    semantic_result = await db.execute(semantic_query.limit(candidate_pool))
    semantic_hits = list(semantic_result.scalars().all())

    tsquery = func.plainto_tsquery("english", query)
    keyword_query = (
        select(DocumentChunk)
        .where(DocumentChunk.content_tsv.op("@@")(tsquery))
        .order_by(func.ts_rank(DocumentChunk.content_tsv, tsquery).desc())
    )
    if document_ids:
        keyword_query = keyword_query.where(DocumentChunk.document_id.in_(document_ids))
    keyword_result = await db.execute(keyword_query.limit(candidate_pool))
    keyword_hits = list(keyword_result.scalars().all())

    scores: dict[UUID, float] = {}
    chunks_by_id: dict[UUID, DocumentChunk] = {}
    for rank_list in (semantic_hits, keyword_hits):
        for rank, chunk in enumerate(rank_list):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (rrf_k + rank + 1)
            chunks_by_id[chunk.id] = chunk

    ranked_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:limit]
    return [SearchHit(chunk=chunks_by_id[cid], score=scores[cid]) for cid in ranked_ids]
