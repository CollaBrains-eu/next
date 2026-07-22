import uuid

from fastapi import HTTPException

from api.ai_gateway import _check_rate_limit


async def test_rate_limit_blocks_after_configured_threshold():
    from api.config import settings

    user_id = uuid.uuid4()
    blocked_at = None
    for i in range(settings.ai_rate_limit_per_minute + 5):
        try:
            await _check_rate_limit(user_id)
        except HTTPException as exc:
            blocked_at = i + 1
            assert exc.status_code == 429
            break

    assert blocked_at == settings.ai_rate_limit_per_minute + 1


async def test_rate_limit_is_per_user():
    from api.config import settings

    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    for _ in range(settings.ai_rate_limit_per_minute):
        await _check_rate_limit(user_a)

    # user_a is now at the limit, but user_b should be unaffected
    await _check_rate_limit(user_b)


async def test_chat_completion_sends_json_format_when_json_mode_enabled(monkeypatch):
    import httpx
    from sqlalchemy import select

    from api.ai_gateway import chat_completion
    from api.db import async_session
    from api.models import User

    username = f"json-mode-test-user-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(User(username=username, display_name="x", role="member"))
        await db.commit()
        result = await db.execute(select(User).where(User.username == username))
        real_user_id = result.scalar_one().id

    captured_request = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "{}"}, "prompt_eval_count": 1, "eval_count": 1}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            captured_request["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    await chat_completion(
        [{"role": "user", "content": "hi"}], user_id=real_user_id, endpoint="test.json_mode", json_mode=True
    )
    assert captured_request["json"]["format"] == "json"

    await chat_completion(
        [{"role": "user", "content": "hi"}], user_id=real_user_id, endpoint="test.no_json_mode", json_mode=False
    )
    assert "format" not in captured_request["json"]


async def test_chat_completion_sends_json_schema_as_format_when_schema_given(monkeypatch):
    import httpx
    from sqlalchemy import select

    from api.ai_gateway import chat_completion
    from api.db import async_session
    from api.models import User

    username = f"schema-test-user-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(User(username=username, display_name="x", role="member"))
        await db.commit()
        result = await db.execute(select(User).where(User.username == username))
        real_user_id = result.scalar_one().id

    captured_request = {}
    schema = {"type": "array", "items": {"type": "object", "properties": {"title": {"type": "string"}}}}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "[]"}, "prompt_eval_count": 1, "eval_count": 1}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            captured_request["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    # schema alone (no json_mode) should still constrain the output shape.
    await chat_completion(
        [{"role": "user", "content": "hi"}], user_id=real_user_id, endpoint="test.schema", schema=schema
    )
    assert captured_request["json"]["format"] == schema

    # schema takes precedence over a bare json_mode=True passed alongside it.
    await chat_completion(
        [{"role": "user", "content": "hi"}],
        user_id=real_user_id,
        endpoint="test.schema_precedence",
        json_mode=True,
        schema=schema,
    )
    assert captured_request["json"]["format"] == schema


async def test_chat_completion_with_tools_sends_tools_and_returns_full_message(monkeypatch):
    import httpx
    from sqlalchemy import select

    from api.ai_gateway import chat_completion_with_tools
    from api.db import async_session
    from api.models import User

    username = f"tools-test-user-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(User(username=username, display_name="x", role="member"))
        await db.commit()
        result = await db.execute(select(User).where(User.username == username))
        real_user_id = result.scalar_one().id

    captured_request = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hi"}}}],
                },
                "prompt_eval_count": 1,
                "eval_count": 1,
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            captured_request["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    tools = [{"type": "function", "function": {"name": "search", "description": "d", "parameters": {}}}]
    message = await chat_completion_with_tools(
        [{"role": "user", "content": "hi"}], user_id=real_user_id, endpoint="test.tools", tools=tools,
    )

    assert captured_request["json"]["tools"] == tools
    assert message["tool_calls"][0]["function"]["name"] == "search"


async def test_chat_completion_without_tools_omits_tools_key_from_request(monkeypatch):
    import httpx
    from sqlalchemy import select

    from api.ai_gateway import chat_completion
    from api.db import async_session
    from api.models import User

    username = f"no-tools-test-user-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(User(username=username, display_name="x", role="member"))
        await db.commit()
        result = await db.execute(select(User).where(User.username == username))
        real_user_id = result.scalar_one().id

    captured_request = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "hello"}, "prompt_eval_count": 1, "eval_count": 1}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            captured_request["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    answer = await chat_completion([{"role": "user", "content": "hi"}], user_id=real_user_id, endpoint="test.plain")

    assert answer == "hello"
    assert "tools" not in captured_request["json"]


async def test_chat_completion_sends_default_num_predict_cap(monkeypatch):
    import httpx
    from sqlalchemy import select

    from api.ai_gateway import chat_completion
    from api.config import settings
    from api.db import async_session
    from api.models import User

    username = f"num-predict-test-user-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(User(username=username, display_name="x", role="member"))
        await db.commit()
        result = await db.execute(select(User).where(User.username == username))
        real_user_id = result.scalar_one().id

    captured_request = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "hi"}, "prompt_eval_count": 1, "eval_count": 1}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            captured_request["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    await chat_completion([{"role": "user", "content": "hi"}], user_id=real_user_id, endpoint="test.num_predict")

    assert captured_request["json"]["options"]["num_predict"] == settings.chat_num_predict
    assert captured_request["json"]["think"] is False


async def test_execute_complex_reasoning_splits_think_block_from_solution(monkeypatch):
    import httpx
    from sqlalchemy import select

    from api.ai_gateway import execute_complex_reasoning
    from api.config import settings
    from api.db import async_session
    from api.models import User

    username = f"reasoning-test-user-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(User(username=username, display_name="x", role="member"))
        await db.commit()
        result = await db.execute(select(User).where(User.username == username))
        real_user_id = result.scalar_one().id

    captured_request = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "message": {"content": "<think>let me work through this</think>The answer is 42."},
                "prompt_eval_count": 1,
                "eval_count": 1,
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            captured_request["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = await execute_complex_reasoning(
        "what is 6*7?", user_id=real_user_id, endpoint="test.reasoning",
    )

    assert result == {"thinking": "let me work through this", "solution": "The answer is 42."}
    sent = captured_request["json"]
    assert sent["model"] == settings.reasoning_model
    assert sent["think"] is True
    assert sent["options"]["temperature"] == 0.4
    assert sent["options"]["num_predict"] == settings.reasoning_num_predict


async def test_execute_complex_reasoning_falls_back_when_no_think_block_present(monkeypatch):
    import httpx
    from sqlalchemy import select

    from api.ai_gateway import execute_complex_reasoning
    from api.db import async_session
    from api.models import User

    username = f"reasoning-fallback-test-user-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(User(username=username, display_name="x", role="member"))
        await db.commit()
        result = await db.execute(select(User).where(User.username == username))
        real_user_id = result.scalar_one().id

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "The answer is 42."}, "prompt_eval_count": 1, "eval_count": 1}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = await execute_complex_reasoning(
        "what is 6*7?", user_id=real_user_id, endpoint="test.reasoning_fallback",
    )

    assert result == {"thinking": "", "solution": "The answer is 42."}


async def test_concurrent_calls_to_ollama_are_serialized(monkeypatch):
    """This deployment's Ollama host runs OLLAMA_NUM_PARALLEL=1: it can only
    process one /api/chat request at a time. When multiple event handlers
    (task/entity/classification/fact extraction) fire off the same
    EMBEDDINGS_CREATED event concurrently, unserialized calls queue up
    *inside Ollama* instead of at the client, so a caller near the back of
    that queue can exceed its own httpx timeout and fail with a ReadTimeout
    or 500 -- confirmed live in production after switching to qwen3:8b
    (5.9GB, much slower than the previous 3B model). Serializing calls
    client-side bounds each call's own wait to "however many callers are
    ahead of it in our own queue", not an opaque server-side one."""
    import asyncio
    import httpx
    from sqlalchemy import select

    from api.ai_gateway import chat_completion
    from api.db import async_session
    from api.models import User

    username = f"concurrency-test-user-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(User(username=username, display_name="x", role="member"))
        await db.commit()
        result = await db.execute(select(User).where(User.username == username))
        real_user_id = result.scalar_one().id

    in_flight = 0
    max_in_flight = 0

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "ok"}, "prompt_eval_count": 1, "eval_count": 1}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.05)
            in_flight -= 1
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    await asyncio.gather(
        *[
            chat_completion(
                [{"role": "user", "content": "hi"}], user_id=real_user_id, endpoint=f"test.concurrency.{i}"
            )
            for i in range(5)
        ]
    )

    assert max_in_flight == 1
