"""Long-term memory: episodic/semantic/procedural facts persisted across
conversations and retrieved by similarity (Phase 8b, ADR 0018).

Retrieval mirrors `search_service.hybrid_search`'s semantic half (embed the
query, order by cosine distance) since memory summaries are short
LLM-generated facts, not long documents with distinct passages -- no
keyword/BM25 half needed here. Creation follows the same shape as
`planner_agent.py`/`entity_agent.py`: a JSON-mode prompt decides whether a
chat exchange revealed anything durable, with graceful degradation on
unparseable model output.
"""
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.embeddings import embed_text
from api.models import Memory

logger = logging.getLogger(__name__)

MEMORY_TYPES = {"episodic", "semantic", "procedural"}
DEFAULT_IMPORTANCE = 50

EXTRACTION_PROMPT = """Decide whether this conversation exchange reveals a durable fact worth \
remembering long-term -- a user preference, an ongoing matter or case, a fact about a specific \
entity, or a reusable plan -- as opposed to a one-off question with no lasting relevance. Return \
ONLY a JSON object (no prose, no markdown fences):

{{"should_remember": bool, "memory_type": "episodic"|"semantic"|"procedural", "summary": str, \
"importance": int}}

"summary" should be a short, self-contained statement of the fact (not a transcript of the \
exchange). "importance" is 0-100, where 100 is critical (e.g. a legal deadline or an identifying \
fact tying an entity to a case) and lower values are minor preferences. If nothing durable is \
worth remembering, return {{"should_remember": false, "memory_type": "episodic", "summary": "", \
"importance": 0}}.

User: {user_message}
Assistant: {answer}"""


async def create_memory(
    db: AsyncSession,
    *,
    user_id: UUID,
    memory_type: str,
    summary: str,
    importance: int = DEFAULT_IMPORTANCE,
    json_data: dict | None = None,
    expires_at: datetime | None = None,
) -> Memory:
    if memory_type not in MEMORY_TYPES:
        raise ValueError(f"invalid memory_type: {memory_type!r}")

    vector = await embed_text(summary)
    memory = Memory(
        user_id=user_id,
        memory_type=memory_type,
        importance=importance,
        summary=summary,
        embedding=vector,
        json_data=json_data,
        expires_at=expires_at,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def retrieve_relevant_memories(
    db: AsyncSession, *, user_id: UUID, query: str, limit: int = 5
) -> list[Memory]:
    """Semantic search over a user's non-expired memories.

    Touches `last_used_at` on every returned memory, which is what
    expiration and any future pruning/consolidation policy would key off.
    """
    query_vector = await embed_text(query)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Memory)
        .where(
            Memory.user_id == user_id,
            or_(Memory.expires_at.is_(None), Memory.expires_at > now),
        )
        .order_by(Memory.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    memories = list(result.scalars().all())
    if memories:
        for memory in memories:
            memory.last_used_at = now
        await db.commit()
    return memories


async def delete_memory(db: AsyncSession, *, memory_id: UUID, user_id: UUID, is_admin: bool = False) -> bool:
    memory = await db.get(Memory, memory_id)
    if memory is None or (memory.user_id != user_id and not is_admin):
        return False
    await db.delete(memory)
    await db.commit()
    return True


async def reinforce_memories(db: AsyncSession, memory_ids: list[UUID], *, delta: int = 5) -> None:
    """Bump importance for memories that contributed to a verified-sufficient
    answer (Phase 12, ADR 0027).

    Reward only, never decay: an insufficient-evidence verdict could be
    about missing document context, not the memory's fault, so there's no
    symmetric penalty here -- see the ADR.
    """
    if not memory_ids:
        return
    result = await db.execute(select(Memory).where(Memory.id.in_(memory_ids)))
    memories = list(result.scalars().all())
    for memory in memories:
        memory.importance = min(100, memory.importance + delta)
    await db.commit()


async def maybe_create_memory_from_exchange(
    db: AsyncSession, *, user_id: UUID, user_message: str, answer: str
) -> Memory | None:
    """Ask the model whether this exchange is worth remembering, and persist it if so.

    Called from a `BackgroundTasks` callback in `chat.py` so the extra LLM
    call never adds latency to the user-visible response.
    """
    prompt = EXTRACTION_PROMPT.format(user_message=user_message[:2000], answer=answer[:2000])
    raw = await chat_completion(
        [{"role": "user", "content": prompt}], user_id=user_id, endpoint="memory.extract", json_mode=True
    )

    try:
        decision = json.loads(raw)
        if not isinstance(decision, dict):
            raise ValueError("expected a JSON object")
    except (json.JSONDecodeError, ValueError):
        logger.warning("memory: could not parse extraction output: %r", raw[:500])
        return None

    if not decision.get("should_remember") or not decision.get("summary"):
        return None

    memory_type = decision.get("memory_type")
    if memory_type not in MEMORY_TYPES:
        memory_type = "episodic"

    importance = decision.get("importance")
    if not isinstance(importance, int) or not 0 <= importance <= 100:
        importance = DEFAULT_IMPORTANCE

    return await create_memory(
        db,
        user_id=user_id,
        memory_type=memory_type,
        summary=str(decision["summary"])[:2000],
        importance=importance,
    )
