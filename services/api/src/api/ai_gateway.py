"""AI Gateway: the one place all LLM calls go through.

Per ADR 0003, this covers model selection (single configured default),
per-user rate limiting (Redis, fixed window), and an audit log of every
call -- not a multi-provider routing layer, since there's exactly one
model/provider in play so far.
"""
import time
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis

from api.config import settings
from api.db import async_session
from api.models import AiCallLog

_redis = Redis.from_url(settings.redis_url)


async def _check_rate_limit(user_id: UUID) -> None:
    key = f"ai_rate_limit:{user_id}"
    count = await _redis.incr(key)
    if count == 1:
        await _redis.expire(key, 60)
    if count > settings.ai_rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI request rate limit exceeded, try again shortly",
        )


async def chat_completion(
    messages: list[dict],
    *,
    user_id: UUID,
    endpoint: str,
    model: str | None = None,
) -> str:
    await _check_rate_limit(user_id)

    chosen_model = model or settings.chat_model
    start = time.monotonic()
    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=120.0) as client:
        response = await client.post(
            "/api/chat",
            json={"model": chosen_model, "messages": messages, "stream": False},
        )
        response.raise_for_status()
        payload = response.json()

    duration_ms = int((time.monotonic() - start) * 1000)

    async with async_session() as db:
        db.add(
            AiCallLog(
                user_id=user_id,
                endpoint=endpoint,
                model=chosen_model,
                prompt_tokens=payload.get("prompt_eval_count"),
                completion_tokens=payload.get("eval_count"),
                duration_ms=duration_ms,
            )
        )
        await db.commit()

    return payload["message"]["content"]
