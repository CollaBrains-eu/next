from datetime import datetime, timezone
from uuid import uuid4

from api.db import async_session
from api.learning_dataset import build_plan_approval_examples, build_reflection_examples, build_training_dataset
from api.models import Plan, PlanStep, ReflectionLog, User


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_approved_legal_plan_step(user_id, *, approved: bool) -> tuple[Plan, PlanStep]:
    async with async_session() as db:
        plan = Plan(
            user_id=user_id, goal_type="draft_legal_document", goal_params={"instruction": "Draft a notice."},
            status="completed", requires_approval=True,
            approved_at=datetime.now(timezone.utc) if approved else None,
        )
        db.add(plan)
        await db.flush()

        step = PlanStep(
            plan_id=plan.id, step_index=0, agent="legal_agent",
            input_data={"instruction": "Draft a notice."},
            status="completed",
            result_data={"draft": "Dear Sir or Madam, ...", "citation_count": 2},
            completed_at=datetime.now(timezone.utc),
        )
        db.add(step)
        await db.commit()
        await db.refresh(plan)
        await db.refresh(step)
        return plan, step


async def test_build_plan_approval_examples_includes_approved_draft():
    user = await _create_user(_unique("learninguser"))
    plan, step = await _create_approved_legal_plan_step(user.id, approved=True)

    async with async_session() as db:
        examples = await build_plan_approval_examples(db, limit=1000)

    matching = [e for e in examples if e["plan_id"] == str(plan.id)]
    assert len(matching) == 1
    example = matching[0]
    assert example["source"] == "plan_approval"
    assert example["input"] == "Draft a notice."
    assert example["output"] == "Dear Sir or Madam, ..."
    assert example["label"] == "approved"


async def test_build_plan_approval_examples_labels_unapproved_plans_correctly():
    user = await _create_user(_unique("learninguser"))
    plan, step = await _create_approved_legal_plan_step(user.id, approved=False)

    async with async_session() as db:
        examples = await build_plan_approval_examples(db, limit=1000)

    matching = [e for e in examples if e["plan_id"] == str(plan.id)]
    assert len(matching) == 1
    assert matching[0]["label"] == "unapproved"


async def test_build_plan_approval_examples_skips_steps_without_result_data():
    user = await _create_user(_unique("learninguser"))
    async with async_session() as db:
        plan = Plan(
            user_id=user.id, goal_type="draft_legal_document", goal_params={"instruction": "x"},
            status="failed", requires_approval=True,
        )
        db.add(plan)
        await db.flush()
        step = PlanStep(
            plan_id=plan.id, step_index=0, agent="legal_agent", input_data={"instruction": "x"},
            status="failed", result_data=None,
        )
        db.add(step)
        await db.commit()
        await db.refresh(plan)

    async with async_session() as db:
        examples = await build_plan_approval_examples(db, limit=1000)

    assert all(e["plan_id"] != str(plan.id) for e in examples)


async def test_build_reflection_examples_includes_real_rows():
    user = await _create_user(_unique("learninguser"))
    question = _unique("What is the deadline?")
    async with async_session() as db:
        db.add(
            ReflectionLog(
                user_id=user.id, endpoint="chat", question=question,
                sufficient_evidence=False, confidence=20, issues=["no evidence"], retried=True,
            )
        )
        await db.commit()

    async with async_session() as db:
        examples = await build_reflection_examples(db, limit=1000)

    matching = [e for e in examples if e["question"] == question]
    assert len(matching) == 1
    assert matching[0]["label"] == "insufficient"
    assert matching[0]["confidence"] == 20


async def test_build_training_dataset_combines_both_sources():
    user = await _create_user(_unique("learninguser"))
    await _create_approved_legal_plan_step(user.id, approved=True)
    async with async_session() as db:
        db.add(
            ReflectionLog(
                user_id=user.id, endpoint="chat", question="Another question?",
                sufficient_evidence=True, confidence=90, issues=[], retried=False,
            )
        )
        await db.commit()

    async with async_session() as db:
        dataset = await build_training_dataset(db, limit=1000)

    assert "generated_at" in dataset
    assert len(dataset["plan_approval_examples"]) >= 1
    assert len(dataset["reflection_examples"]) >= 1
