"""Planner Agent: extract actionable tasks from a document's text (ADR 0004).

Originally deliberately narrow scope -- task extraction, not scheduling (see
the ADR for what was out of scope: calendar sync, recurrence, real user
assignment). Recurrence was added in ADR 0064; calendar sync was added here
-- an appointment-category task now creates a linked Appointment via
calendar_sync.sync_appointment_for_task once it's committed.
"""
import json
import logging
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.calendar_sync import sync_appointment_for_task
from api.models import TASK_CATEGORIES, Task

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract actionable tasks from the following document. \
This includes explicit to-dos AND any scheduled appointment, deadline, or date \
the reader needs to act on or attend -- e.g. a line saying an appointment has \
been booked for a given date counts as a task like "Attend appointment on \
[date]", even if the document never phrases it as an instruction. \
Return ONLY a JSON array (no prose, no markdown fences), where each item has:
- "title": short imperative description (required)
- "description": one sentence of extra context, or null
- "due_date": an ISO date "YYYY-MM-DD" if a concrete date is mentioned, otherwise null
- "assignee": a person or role name if mentioned, otherwise null
- "category": one of {categories} if the task clearly fits one, otherwise null

If there are truly no actionable tasks or dates to act on, return an empty array: []

Document:
{text}"""

EXTRACTION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": ["string", "null"]},
            "due_date": {"type": ["string", "null"]},
            "assignee": {"type": ["string", "null"]},
            "category": {"type": ["string", "null"], "enum": [*TASK_CATEGORIES, None]},
        },
        "required": ["title"],
    },
}


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
    prompt = EXTRACTION_PROMPT.format(text=text[:8000], categories=" | ".join(f'"{c}"' for c in TASK_CATEGORIES))
    raw = await chat_completion(
        [{"role": "user", "content": prompt}],
        user_id=user_id,
        endpoint="planner.extract_tasks",
        schema=EXTRACTION_SCHEMA,
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
        category = item.get("category")
        if category not in TASK_CATEGORIES:
            category = None
        task = Task(
            document_id=document_id,
            title=str(item["title"])[:500],
            description=item.get("description") or None,
            due_date=_parse_due_date(item.get("due_date")),
            assignee=item.get("assignee") or None,
            category=category,
            source=source,
            created_by=user_id,
        )
        db.add(task)
        tasks.append(task)

    if tasks:
        await db.commit()
        for task in tasks:
            await db.refresh(task)
            await sync_appointment_for_task(db, task=task, user_id=user_id)
    return tasks
