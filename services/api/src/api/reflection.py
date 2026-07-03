"""Reflection Engine: post-hoc review of generated answers (Phase 8d, ADR 0020).

A second, independent LLM call judges whether a just-generated answer is
actually backed by the context it was given. Callers use this to decide
whether to retry retrieval with a wider net, and to keep an audit trail of
how often the system flags its own answers as under-evidenced.
"""
import json
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.models import ReflectionLog

logger = logging.getLogger(__name__)

REFLECTION_SYSTEM_PROMPT = (
    "You are a fact-checking reviewer. You will see a question, the context "
    "excerpts that were available, and an answer that was generated from that "
    "context. Judge whether the context contained enough evidence to answer "
    "the question, and whether every claim in the answer is backed by the "
    "context. Respond with ONLY a JSON object of the form "
    '{"sufficient_evidence": true or false, "confidence": integer 0-100, '
    '"issues": [list of short strings, empty if none]}. sufficient_evidence '
    "must be false if the context lacks the facts needed to answer the "
    "question, or if the answer makes claims the context does not support."
)


@dataclass
class ReflectionResult:
    sufficient_evidence: bool
    confidence: int
    issues: list[str]


def _fallback_result(reason: str) -> ReflectionResult:
    """Permissive default used when reflection itself can't produce a verdict.

    Defaults to trusting the original answer rather than forcing a retry --
    an unreliable reflection step should degrade to a no-op, not to extra
    retries on every request.
    """
    logger.warning("reflection could not produce a verdict (%s); defaulting to sufficient_evidence=True", reason)
    return ReflectionResult(sufficient_evidence=True, confidence=100, issues=[])


async def reflect(
    *,
    question: str,
    answer: str,
    context_text: str,
    user_id: UUID,
    endpoint: str,
) -> ReflectionResult:
    messages = [
        {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {question}\n\nContext:\n{context_text}\n\nAnswer:\n{answer}"},
    ]
    raw = await chat_completion(messages, user_id=user_id, endpoint=f"{endpoint}.reflection", json_mode=True)

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _fallback_result("unparseable JSON")

    if not isinstance(parsed, dict):
        return _fallback_result("JSON was not an object")

    sufficient_evidence = parsed.get("sufficient_evidence")
    if not isinstance(sufficient_evidence, bool):
        return _fallback_result("missing/invalid sufficient_evidence")

    confidence = parsed.get("confidence")
    if not isinstance(confidence, int) or isinstance(confidence, bool):
        confidence = 100 if sufficient_evidence else 0
    confidence = max(0, min(100, confidence))

    issues = parsed.get("issues")
    if not isinstance(issues, list) or not all(isinstance(item, str) for item in issues):
        issues = []

    return ReflectionResult(sufficient_evidence=sufficient_evidence, confidence=confidence, issues=issues)


async def log_reflection(
    db: AsyncSession,
    *,
    user_id: UUID,
    endpoint: str,
    question: str,
    result: ReflectionResult,
    retried: bool,
) -> None:
    db.add(
        ReflectionLog(
            user_id=user_id,
            endpoint=endpoint,
            question=question,
            sufficient_evidence=result.sufficient_evidence,
            confidence=result.confidence,
            issues=result.issues,
            retried=retried,
        )
    )
    await db.commit()
