"""In-process event bus with durable Redis Stream logging (Phase 8a, ADR 0017).

Handlers run inline -- awaited as part of `publish()` -- rather than via a
separate consumer-group polling loop. Every publisher and subscriber for the
initial event set lives in the same process as the rest of `services/api`,
so a second process reading a shared stream has no consumer yet; see ADR
0017 for why this mirrors ADR 0004's "in-process trigger, not Celery yet"
reasoning. Every publish still durably appends to a Redis Stream, so retry
accounting, the dead-letter queue, and audit history are real, and dispatch
can move to a cross-process consumer group later without changing any
`publish()` call site.
"""
import asyncio
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from api.config import settings

logger = logging.getLogger(__name__)

STREAM_PREFIX = "collabrains:events"
SEEN_PREFIX = "collabrains:events:seen"
SEEN_TTL_SECONDS = 24 * 60 * 60
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = (1, 5, 15)
LOGGED_VALUE_MAX_LENGTH = 500


class EventType:
    """The initial event set from the Phase 8a roadmap."""

    DOCUMENT_UPLOADED = "DocumentUploaded"
    OCR_COMPLETED = "OCRCompleted"
    EMBEDDINGS_CREATED = "EmbeddingsCreated"
    SUMMARY_CREATED = "SummaryCreated"
    ENTITIES_EXTRACTED = "EntitiesExtracted"
    VEHICLES_DETECTED = "VehiclesDetected"
    DOCUMENT_CLASSIFIED = "DocumentClassified"
    FACTS_EXTRACTED = "FactsExtracted"
    TASKS_CREATED = "TasksCreated"
    NOTIFICATION_REQUESTED = "NotificationRequested"
    WORKFLOW_STARTED = "WorkflowStarted"
    WORKFLOW_COMPLETED = "WorkflowCompleted"


def _redact_for_log(value: Any) -> Any:
    """Summarize bulky/binary payload values before they hit the audit log.

    Full values (e.g. raw document bytes, full OCR text) still reach
    in-process handlers via `Event.payload` -- only the durable Redis
    Stream record is trimmed, since that log is for audit/retry/DLQ
    bookkeeping, not for replaying large document content.
    """
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, str) and len(value) > LOGGED_VALUE_MAX_LENGTH:
        return f"{value[:LOGGED_VALUE_MAX_LENGTH]}... <{len(value)} chars total>"
    return value


class Event:
    def __init__(self, event_type: str, payload: dict[str, Any], event_id: str | None = None):
        self.event_type = event_type
        self.payload = payload
        self.event_id = event_id or str(uuid.uuid4())
        self.created_at = datetime.now(timezone.utc)

    def to_stream_fields(self) -> dict[str, str]:
        safe_payload = {key: _redact_for_log(value) for key, value in self.payload.items()}
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": json.dumps(safe_payload, default=str),
            "created_at": self.created_at.isoformat(),
        }


Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self, redis: Redis):
        self._redis = redis
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> Event:
        event = Event(event_type, payload)
        stream = f"{STREAM_PREFIX}:{event_type}"
        await self._redis.xadd(stream, event.to_stream_fields())
        logger.info("event published: type=%s id=%s", event_type, event.event_id)

        for handler in self._subscribers.get(event_type, []):
            await self._dispatch(handler, event, stream)
        return event

    async def _dispatch(self, handler: Handler, event: Event, stream: str) -> None:
        handler_name = getattr(handler, "__qualname__", repr(handler))
        seen_key = f"{SEEN_PREFIX}:{event.event_id}:{handler_name}"
        if not await self._redis.set(seen_key, "1", nx=True, ex=SEEN_TTL_SECONDS):
            logger.info("event %s already processed by %s, skipping (idempotent)", event.event_id, handler_name)
            return

        for attempt in range(MAX_RETRIES + 1):
            try:
                await handler(event)
                return
            except Exception:  # noqa: BLE001 - a subscriber failure must never crash the publisher
                if attempt < MAX_RETRIES:
                    delay = RETRY_BACKOFF_SECONDS[attempt]
                    logger.warning(
                        "handler %s failed for event %s (attempt %d/%d), retrying in %ss",
                        handler_name, event.event_id, attempt + 1, MAX_RETRIES, delay, exc_info=True,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.exception(
                        "handler %s exhausted retries for event %s, moving to DLQ", handler_name, event.event_id
                    )
                    await self._redis.xadd(f"{stream}:dlq", event.to_stream_fields())
                    # Don't leave this permanently marked "seen" -- a DLQ
                    # replay should be able to re-dispatch it.
                    await self._redis.delete(seen_key)


_bus: EventBus | None = None


def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus(Redis.from_url(settings.redis_url))
    return _bus


async def publish(event_type: str, payload: dict[str, Any]) -> Event:
    return await get_bus().publish(event_type, payload)


def subscribe(event_type: str) -> Callable[[Handler], Handler]:
    """Decorator: register a handler for `event_type` at import time."""

    def decorator(handler: Handler) -> Handler:
        get_bus().subscribe(event_type, handler)
        return handler

    return decorator
