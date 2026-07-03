"""Learning Platform: dataset export from real feedback signal (Phase 15,
ADR 0030).

Only Feedback -> Evaluation -> Dataset are built. Synthetic Data, Fine
Tune, Benchmark, and Deploy are deliberately not attempted -- this
environment has no training framework and no compute budget to spare
(ADR 0015's load test already found this host CPU-bound at 8 concurrent
chat users); see the ADR for why faking those stages would be worse
than not building them.
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Plan, PlanStep, ReflectionLog


async def build_plan_approval_examples(db: AsyncSession, *, limit: int = 100) -> list[dict[str, Any]]:
    """Completed legal_agent steps: a real (instruction -> draft) pair,
    labeled by whether a human actually approved the plan it belongs to.
    """
    result = await db.execute(
        select(PlanStep, Plan)
        .join(Plan, PlanStep.plan_id == Plan.id)
        .where(PlanStep.agent == "legal_agent", PlanStep.status == "completed")
        .order_by(PlanStep.completed_at.desc())
        .limit(limit)
    )

    examples: list[dict[str, Any]] = []
    for step, plan in result.all():
        if not step.input_data or not step.result_data:
            continue
        examples.append({
            "source": "plan_approval",
            "plan_id": str(plan.id),
            "input": step.input_data.get("instruction"),
            "output": step.result_data.get("draft"),
            "label": "approved" if plan.approved_at is not None else "unapproved",
            "created_at": step.completed_at.isoformat() if step.completed_at else None,
        })
    return examples


async def build_reflection_examples(db: AsyncSession, *, limit: int = 100) -> list[dict[str, Any]]:
    """ReflectionLog rows as quality-evaluation signal.

    Not an input/output pair -- ReflectionLog never stored the answer
    text, only the verdict (ADR 0020) -- but a real signal for which
    kinds of questions the system judges its own answers insufficient
    for.
    """
    result = await db.execute(
        select(ReflectionLog).order_by(ReflectionLog.created_at.desc()).limit(limit)
    )

    return [
        {
            "source": "reflection",
            "question": log.question,
            "label": "sufficient" if log.sufficient_evidence else "insufficient",
            "confidence": log.confidence,
            "issues": log.issues,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in result.scalars().all()
    ]


async def build_training_dataset(db: AsyncSession, *, limit: int = 100) -> dict[str, Any]:
    """The full Phase 15 dataset export: both real signal sources, versioned
    by generation time. No synthetic augmentation -- see the ADR.
    """
    plan_approval_examples = await build_plan_approval_examples(db, limit=limit)
    reflection_examples = await build_reflection_examples(db, limit=limit)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan_approval_examples": plan_approval_examples,
        "reflection_examples": reflection_examples,
    }
