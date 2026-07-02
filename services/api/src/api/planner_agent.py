"""Planner Agent: extract actionable tasks from a document's text (ADR 0004).

Deliberately narrow scope -- task extraction, not scheduling. See the ADR
for what's out of scope (calendar sync, recurrence, real user assignment).
"""
import json
import logging
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.models import Task

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract actionable tasks from the following document. \
Return ONLY a JSON array (no prose, no markdown fences), where each item has:
- "title": short imperative description (required)
- "description": one sentence of extra context, or null
- "due_date": an ISO date "YYYY-MM-DD" if a concrete date is mentioned, otherwise null
- "assignee": a person or role name if mentioned, otherwise null

If there are no actionable tasks, return an empty array: []

Document:
{text}"""


def _parse_due_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def extract_tasks(
    db: AsyncSession,
    *,
    document_id: UUID,
    text: str,
    user_id: UUID | None,
    source: str = "planner_agent",
) -> list[Task]:
    """Extract tasks from `text` via the AI Gateway and persist them.

    `user_id` is required by the AI Gateway for rate limiting/audit even
    when this runs from a background trigger with no requesting user in
    the loop -- callers pass the document's owner in that case.
    """
    prompt = EXTRACTION_PROMPT.format(text=text[:8000])
    raw = await chat_completion(
        [{"role": "user", "content": prompt}],
        user_id=user_id,
        endpoint="planner.extract_tasks",
        json_mode=True,
    )

    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError("expected a JSON array")
    except (json.JSONDecodeError, ValueError):
        logger.warning("planner_agent: could not parse task extraction output: %r", raw[:500])
        return []

    tasks: list[Task] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        task = Task(
            document_id=document_id,
            title=str(item["title"])[:500],
            description=item.get("description") or None,
            due_date=_parse_due_date(item.get("due_date")),
            assignee=item.get("assignee") or None,
            source=source,
            created_by=user_id,
        )
        db.add(task)
        tasks.append(task)

    if tasks:
        await db.commit()
        for task in tasks:
            await db.refresh(task)
    return tasks
