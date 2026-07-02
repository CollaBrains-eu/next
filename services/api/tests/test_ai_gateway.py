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

    async with async_session() as db:
        db.add(User(username="json-mode-test-user", display_name="x", role="member"))
        await db.commit()
        result = await db.execute(select(User).where(User.username == "json-mode-test-user"))
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
