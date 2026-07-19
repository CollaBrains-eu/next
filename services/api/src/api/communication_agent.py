"""Communication Agent: grounded message drafting from ingested documents (Phase 24).

The last missing link in the Trigger -> Planner -> Legal -> Document ->
Communication -> Notification chain the original spec described --
Planning Engine (ADR 0019) already dispatches every other step in that
chain, `communication_agent` was the one `agents/communication-agent/`
stub with no implementation behind it.

Grounded the same way Legal Agent is (ADR 0004): drafts only from
retrieved document context, never invents facts. Does not use the
Reflection Engine (ADR 0020) -- that exists for claims a reader could act
on as fact (legal drafts, research answers); a communication draft is
reviewed by its sender before sending regardless, so the extra LLM call
isn't proportionate here.
"""
import json
import logging
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.preferences import get_preferences
from api.search_service import hybrid_search
from api.text_language import ts_config_for_preferred_language

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You draft short messages (Signal or email) using ONLY the provided context excerpts "
    "as your factual basis. Never invent facts, names, or details not present in the "
    "context. If the context is insufficient, write a message that says so explicitly "
    "instead of filling gaps with assumptions."
)


class CommunicationDraft(BaseModel):
    channel: str
    recipient: str
    subject: str | None
    body: str


async def draft_communication(
    db: AsyncSession, *, instruction: str, channel: str, recipient: str, user_id: UUID,
    document_ids: list[UUID] | None = None,
) -> CommunicationDraft:
    if channel not in {"signal", "email"}:
        raise ValueError(f"unknown channel: {channel!r}")

    scope = set(document_ids) if document_ids else None
    preferences = await get_preferences(db, user_id=user_id)
    language = ts_config_for_preferred_language(preferences.preferred_language if preferences else None)
    hits = await hybrid_search(db, instruction, limit=8, owner_id=user_id, document_ids=scope, language=language)
    context_text = (
        "\n\n".join(f"[{i}] {hit.chunk.content}" for i, hit in enumerate(hits, start=1))
        if hits else "(no relevant documents found)"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Context:\n{context_text}\n\nChannel: {channel}\nRecipient: {recipient}\n"
                f"Drafting instruction: {instruction}\n\n"
                'Return ONLY a JSON object (no prose, no markdown fences) with this shape: '
                '{"subject": str|null, "body": str}. "subject" is null for Signal (no subject line).'
            ),
        },
    ]
    raw = await chat_completion(messages, user_id=user_id, endpoint="communication.draft", json_mode=True)

    try:
        payload = json.loads(raw)
        body = str(payload["body"])
        subject = payload.get("subject")
        subject = str(subject) if subject else None
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("communication_agent: could not parse draft output: %r", raw[:500])
        body = raw
        subject = None

    return CommunicationDraft(channel=channel, recipient=recipient, subject=subject, body=body)
