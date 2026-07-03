from unittest.mock import patch

from redis.asyncio import Redis

from api.config import settings
from api.events import Event, EventBus


def _make_bus() -> EventBus:
    return EventBus(Redis.from_url(settings.redis_url))


async def test_publish_dispatches_to_subscriber_with_full_payload():
    bus = _make_bus()
    received = []

    async def handler(event: Event) -> None:
        received.append(event.payload)

    bus.subscribe("TestEvent", handler)
    await bus.publish("TestEvent", {"foo": "bar", "content": b"raw bytes here"})

    assert received == [{"foo": "bar", "content": b"raw bytes here"}]


async def test_publish_appends_a_redacted_record_to_the_redis_stream():
    bus = _make_bus()
    long_text = "x" * 2000
    event = await bus.publish("TestEvent", {"content": b"raw bytes", "text": long_text, "n": 3})

    stream = "collabrains:events:TestEvent"
    entries = await bus._redis.xrange(stream)
    ids = [fields[b"event_id"].decode() for _, fields in entries]
    assert event.event_id in ids

    logged = next(fields for _, fields in entries if fields[b"event_id"].decode() == event.event_id)
    assert b"<9 bytes>" in logged[b"payload"]
    assert b"chars total" in logged[b"payload"]
    assert long_text.encode() not in logged[b"payload"]


async def test_handler_failure_retries_then_moves_to_dlq_without_raising():
    bus = _make_bus()
    calls = []

    async def always_fails(event: Event) -> None:
        calls.append(event.event_id)
        raise RuntimeError("boom")

    bus.subscribe("FlakyEvent", always_fails)

    with patch("api.events.RETRY_BACKOFF_SECONDS", (0, 0, 0)):
        event = await bus.publish("FlakyEvent", {"x": 1})

    assert len(calls) == 4  # initial attempt + 3 retries

    dlq_entries = await bus._redis.xrange("collabrains:events:FlakyEvent:dlq")
    dlq_ids = [fields[b"event_id"].decode() for _, fields in dlq_entries]
    assert event.event_id in dlq_ids


async def test_dispatch_is_idempotent_per_event_and_handler():
    bus = _make_bus()
    calls = []

    async def handler(event: Event) -> None:
        calls.append(event.event_id)

    event = Event("RepeatedEvent", {"x": 1})
    await bus._dispatch(handler, event, "collabrains:events:RepeatedEvent")
    await bus._dispatch(handler, event, "collabrains:events:RepeatedEvent")

    assert calls == [event.event_id]


async def test_one_subscriber_failing_does_not_block_another():
    bus = _make_bus()
    second_handler_called = []

    async def failing_handler(event: Event) -> None:
        raise RuntimeError("first subscriber is broken")

    async def other_handler(event: Event) -> None:
        second_handler_called.append(event.event_id)

    bus.subscribe("MultiSubEvent", failing_handler)
    bus.subscribe("MultiSubEvent", other_handler)

    with patch("api.events.RETRY_BACKOFF_SECONDS", (0, 0, 0)):
        event = await bus.publish("MultiSubEvent", {})

    assert second_handler_called == [event.event_id]
