"""Due-task Signal notifications (ADR 0064).

Run daily via host cron, same shape as infra/monitoring/watchdog.sh and
infra/backup/backup.sh, but invoked inside the API container since it
needs the app's models and Signal client:

    docker compose exec -T api python -m api.scripts.notify_due_tasks

Notifies a task's creator (not `assignee`, which is free text with no
guaranteed link to a real user -- see ADR 0064) when the task is due
today or overdue, mirroring documents.py's _notify_owner. Every send is
wrapped so one failure (a transient Signal error, a task whose creator
has no linked phone) can never stop the rest of the batch -- the
project-wide contract for this notification channel (signal_client.py's
own docstring: "every caller must treat a failure here as non-fatal").
"""
import asyncio
import logging
from datetime import date, datetime, timezone

from sqlalchemy import select

from api.db import async_session
from api.models import Task, User
from api.signal_client import send_signal_message

logger = logging.getLogger(__name__)


def _message_for(task: Task, today: date) -> str:
    if task.due_date < today:
        days = (today - task.due_date).days
        return f'Task "{task.title}" is overdue by {days} day{"s" if days != 1 else ""}.'
    return f'Task "{task.title}" is due today.'


async def notify_due_tasks() -> int:
    """Returns the number of notifications actually sent, for cron log visibility."""
    today = datetime.now(timezone.utc).date()
    sent = 0

    async with async_session() as db:
        result = await db.execute(
            select(Task).where(
                Task.status != "done",
                Task.due_date.is_not(None),
                Task.due_date <= today,
                Task.notified_at.is_(None),
            )
        )
        due_tasks = list(result.scalars().all())

        for task in due_tasks:
            try:
                if task.created_by is None:
                    continue
                owner = await db.get(User, task.created_by)
                if owner is None or not owner.phone_number:
                    continue
                await send_signal_message(owner.phone_number, _message_for(task, today))
                task.notified_at = datetime.now(timezone.utc)
                sent += 1
            except Exception:
                logger.exception("failed to send due-task notification for task %s", task.id)

        await db.commit()

    return sent


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = asyncio.run(notify_due_tasks())
    logger.info("sent %d due-task notification(s)", count)
