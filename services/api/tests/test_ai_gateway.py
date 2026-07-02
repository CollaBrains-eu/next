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
