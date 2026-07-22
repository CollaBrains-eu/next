"""AI Gateway: the one place all LLM calls go through.

Per ADR 0003, this covers model selection (single configured default),
per-user rate limiting (Redis, fixed window), and an audit log of every
call -- not a multi-provider routing layer, since there's exactly one
model/provider in play so far.

chat_completion_with_tools (Phase 9d, ADR 0024) shares the same
rate-limit/call/audit-log machinery via _call_ollama, but returns the
raw response message (content + optional tool_calls) instead of just
the content string -- chat_completion's contract is unchanged for its
many existing callers.

execute_complex_reasoning (see docs/deployment/ai-optimization.md) also
shares _call_ollama, but targets settings.reasoning_model (deepseek-r1)
with thinking enabled and splits the chain-of-thought out of the final
answer.
"""
import asyncio
import re
import time
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis

from api.config import settings
from api.db import async_session
from api.models import AiCallLog

_redis = Redis.from_url(settings.redis_url)

# This deployment's Ollama host serves one /api/chat request at a time
# (OLLAMA_NUM_PARALLEL=1, confirmed in its own startup log -- a resource
# constraint of the CPU-only host, not something this app configures).
# Multiple event handlers fire off the same EMBEDDINGS_CREATED event
# concurrently (task/entity/classification/fact extraction); without this,
# their calls queue up *inside Ollama* instead of at the client, so a
# caller near the back of that queue can exceed its own httpx timeout and
# fail with a ReadTimeout or 500 -- confirmed live after switching to
# qwen3:8b, a much slower model than the one this was originally tuned
# against. Serializing client-side bounds each call's wait to "how many
# callers this process itself has ahead of it," not an opaque server queue.
_ollama_semaphore = asyncio.Semaphore(1)


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


async def _call_ollama(
    messages: list[dict],
    *,
    user_id: UUID,
    endpoint: str,
    model: str | None,
    json_mode: bool,
    schema: dict[str, Any] | None,
    tools: list[dict[str, Any]] | None,
    think: bool = False,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await _check_rate_limit(user_id)

    chosen_model = model or settings.chat_model
    start = time.monotonic()
    async with _ollama_semaphore:
        async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=settings.ollama_timeout_seconds) as client:
            # think=False (the default): qwen2.5-coder/qwen3-family models otherwise
            # emit a full chain-of-thought before every answer -- ~30s for a trivial
            # prompt on this CPU-only host vs ~1.8s with thinking off. Harmless no-op
            # for non-thinking models. execute_complex_reasoning explicitly overrides
            # this to True since its whole point is capturing that chain-of-thought.
            #
            # num_predict caps every response to bound worst-case generation time and
            # memory on this 4-vCPU/8GB host with no swap (see
            # docs/deployment/ai-optimization.md) -- unset previously, so a runaway
            # generation had no hard stop. Caller-supplied `options` (e.g.
            # execute_complex_reasoning's temperature/num_predict) take precedence.
            request_body: dict[str, Any] = {
                "model": chosen_model, "messages": messages, "stream": False, "think": think,
                "options": {"num_predict": settings.chat_num_predict, **(options or {})},
            }
            if schema is not None:
                # Structured outputs (Ollama >=0.5): a real JSON schema, not just
                # "some JSON" -- format="json" alone lets a model return a bare
                # object where an array was asked for (or vice versa), which then
                # fails an isinstance() check downstream and gets silently
                # discarded. Confirmed live against this deployment's own models:
                # both qwen2.5:3b-instruct and qwen3:8b did exactly this on an
                # array-shaped prompt when only given format="json".
                request_body["format"] = schema
            elif json_mode:
                request_body["format"] = "json"
            if tools:
                request_body["tools"] = tools
            response = await client.post("/api/chat", json=request_body)
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

    return payload["message"]


async def chat_completion(
    messages: list[dict],
    *,
    user_id: UUID,
    endpoint: str,
    model: str | None = None,
    json_mode: bool = False,
    schema: dict[str, Any] | None = None,
) -> str:
    """Set json_mode=True for prompts that require valid JSON output, or pass
    `schema` (a JSON Schema dict) when the output has a specific shape --
    schema is strictly stronger and implies json_mode, so callers with a
    known shape should prefer it over bare json_mode=True.

    Uses Ollama's grammar-constrained JSON decoding rather than relying on
    prompt instructions alone -- a small model asked only in the prompt to
    "return JSON" can and does occasionally produce malformed output
    (mismatched braces, missing closing brackets), or valid-but-wrong-shaped
    JSON (an object where an array was asked for). Confirmed directly: the
    Entity Agent's extraction prompt (docs/adr/0008-phase4-entity-graph.md)
    hit the malformed-output case on its first live test; the wrong-shape
    case was confirmed live against this deployment's own models while
    diagnosing why task extraction silently produced nothing for real
    documents.
    """
    message = await _call_ollama(
        messages, user_id=user_id, endpoint=endpoint, model=model, json_mode=json_mode, schema=schema, tools=None,
    )
    return message["content"]


async def chat_completion_with_tools(
    messages: list[dict],
    *,
    user_id: UUID,
    endpoint: str,
    tools: list[dict[str, Any]],
    model: str | None = None,
) -> dict[str, Any]:
    """Like chat_completion, but offers the model a set of callable tools
    (Phase 9d, ADR 0024) via Ollama's native function-calling and returns
    the raw response message instead of just its content -- callers must
    check for a "tool_calls" key themselves.

    Executing a requested tool call (looking it up in the registry,
    dispatching it, feeding a result back for a second round-trip) is
    deliberately not this function's job -- see ADR 0024 for why that loop
    is out of scope here.
    """
    return await _call_ollama(
        messages, user_id=user_id, endpoint=endpoint, model=model, json_mode=False, schema=None, tools=tools,
    )


_THINK_BLOCK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def _split_thinking(content: str, message: dict[str, Any]) -> tuple[str, str]:
    """Split a reasoning model's raw output into (thinking, solution).

    deepseek-r1 (via Ollama) emits its chain-of-thought inline as a
    <think>...</think> block at the start of message.content by default.
    Some Ollama versions instead return it in a separate message.thinking
    field when think=True is requested -- checked as a fallback since
    which shape a given Ollama version returns isn't controlled by this app.
    Falls back to an empty thinking string (not an error) if neither shape
    is present, since a reasoning model can still answer directly.
    """
    match = _THINK_BLOCK_RE.search(content)
    if match:
        thinking = match.group(1).strip()
        solution = _THINK_BLOCK_RE.sub("", content).strip()
        return thinking, solution

    thinking = (message.get("thinking") or "").strip()
    return thinking, content.strip()


async def execute_complex_reasoning(prompt: str, *, user_id: UUID, endpoint: str) -> dict[str, str]:
    """Run a prompt through settings.reasoning_model (deepseek-r1) with thinking
    enabled, and separate its chain-of-thought from the final answer.

    `thinking` is for logging/admin visibility only -- never shown to end users
    unvetted, since a reasoning model's intermediate steps carry the same
    hallucination risk chat_completion's docstring warns about, just not yet
    cleaned up into a final answer. `solution` is what callers should show users.
    temperature=0.4 (vs. the Ollama default of 0.8) favors consistency over
    creativity for reasoning/logic tasks; num_predict=reasoning_num_predict
    (1024, double chat's 512) gives the chain-of-thought room to finish before
    the hard cutoff, since truncating mid-thought would otherwise strip the
    final answer entirely.
    """
    message = await _call_ollama(
        [{"role": "user", "content": prompt}],
        user_id=user_id,
        endpoint=endpoint,
        model=settings.reasoning_model,
        json_mode=False,
        schema=None,
        tools=None,
        think=True,
        options={"temperature": 0.4, "num_predict": settings.reasoning_num_predict},
    )
    thinking, solution = _split_thinking(message.get("content", ""), message)
    return {"thinking": thinking, "solution": solution}
