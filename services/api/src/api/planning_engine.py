"""Planning Engine: goal -> task tree -> sequential agent execution (Phase 8c, ADR 0019).

Goal decomposition is a fixed, deterministic template per `goal_type`
parameterized by `goal_params` -- not an LLM improvising the plan
structure. See the ADR for why: the same "smallest safe slice" reasoning
ADR 0004 applied to the Legal Agent applies to plan *structure* here, and
none of the six initial goals need dynamic structure. Each step dispatches
to an existing agent (Document/Planner/Entity/Legal Agent) or one of two
new deterministic aggregations (`organize_document_collection`,
`generate_timeline`) that need no LLM call at all.
"""
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.documents import _generate_summary
from api.entity_agent import extract_entities
from api.knowledge_graph import create_decision_from_plan
from api.legal import _generate_draft
from api.models import Document, Entity, EntityMention, Plan, PlanStep, Task
from api.organizations import get_approval_required_goals
from api.planner_agent import extract_tasks

logger = logging.getLogger(__name__)

GOAL_TYPES = {
    "summarize_case",
    "draft_legal_document",
    "prepare_objection",
    "analyze_new_upload",
    "organize_document_collection",
    "generate_timeline",
}

APPROVAL_REQUIRED_GOALS = {"draft_legal_document", "prepare_objection"}

MAX_STEP_ATTEMPTS = 2


def _require_document_ids(goal_params: dict[str, Any], goal_type: str) -> list[str]:
    document_ids = goal_params.get("document_ids") or []
    if not document_ids:
        raise ValueError(f"{goal_type} requires at least one document_id")
    return document_ids


def build_steps(goal_type: str, goal_params: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the fixed step template for `goal_type`, parameterized by `goal_params`."""
    if goal_type == "summarize_case":
        document_ids = _require_document_ids(goal_params, goal_type)
        return [{"agent": "document_agent", "input_data": {"document_id": doc_id}} for doc_id in document_ids]

    if goal_type == "analyze_new_upload":
        document_id = goal_params.get("document_id")
        if not document_id:
            raise ValueError("analyze_new_upload requires a document_id")
        return [
            {"agent": "document_agent", "input_data": {"document_id": document_id}},
            {"agent": "planner_agent", "input_data": {"document_id": document_id}},
            {"agent": "entity_agent", "input_data": {"document_id": document_id}},
        ]

    if goal_type == "draft_legal_document":
        instruction = goal_params.get("instruction")
        if not instruction:
            raise ValueError("draft_legal_document requires an instruction")
        return [
            {
                "agent": "legal_agent",
                "input_data": {"instruction": instruction, "document_ids": goal_params.get("document_ids", [])},
            }
        ]

    if goal_type == "prepare_objection":
        grounds = goal_params.get("grounds", "")
        instruction = f"Draft an objection. Grounds: {grounds}" if grounds else "Draft an objection."
        return [
            {
                "agent": "legal_agent",
                "input_data": {"instruction": instruction, "document_ids": goal_params.get("document_ids", [])},
            }
        ]

    if goal_type == "organize_document_collection":
        document_ids = _require_document_ids(goal_params, goal_type)
        return [{"agent": "collection_agent", "input_data": {"document_ids": document_ids}}]

    if goal_type == "generate_timeline":
        document_ids = _require_document_ids(goal_params, goal_type)
        return [{"agent": "timeline_agent", "input_data": {"document_ids": document_ids}}]

    raise ValueError(f"unknown goal_type: {goal_type!r}")


async def organize_document_collection(db: AsyncSession, document_ids: list[UUID]) -> dict[str, Any]:
    """Group the given documents' mentioned entities by type. A pure DB aggregation, no LLM call."""
    documents_result = await db.execute(select(Document).where(Document.id.in_(document_ids)))
    documents = list(documents_result.scalars().all())

    mentions_result = await db.execute(select(EntityMention).where(EntityMention.document_id.in_(document_ids)))
    entity_ids = {mention.entity_id for mention in mentions_result.scalars().all()}

    entities_by_type: dict[str, list[str]] = {}
    if entity_ids:
        entities_result = await db.execute(select(Entity).where(Entity.id.in_(entity_ids)))
        for entity in entities_result.scalars().all():
            entities_by_type.setdefault(entity.entity_type, []).append(entity.name)

    return {
        "document_count": len(documents),
        "documents": [{"id": str(doc.id), "title": doc.title, "status": doc.status} for doc in documents],
        "entities_by_type": entities_by_type,
    }


async def generate_timeline(db: AsyncSession, document_ids: list[UUID]) -> list[dict[str, Any]]:
    """Chronologically order document uploads and task due dates. A pure DB aggregation, no LLM call."""
    documents_result = await db.execute(select(Document).where(Document.id.in_(document_ids)))
    documents = list(documents_result.scalars().all())

    tasks_result = await db.execute(
        select(Task).where(Task.document_id.in_(document_ids), Task.due_date.isnot(None))
    )
    tasks = list(tasks_result.scalars().all())

    events: list[dict[str, Any]] = []
    for document in documents:
        events.append(
            {
                "date": document.created_at.date().isoformat(),
                "kind": "document_uploaded",
                "description": f'Document "{document.title}" uploaded',
                "document_id": str(document.id),
            }
        )
    for task in tasks:
        events.append(
            {
                "date": task.due_date.isoformat(),
                "kind": "task_due",
                "description": task.title,
                "document_id": str(task.document_id) if task.document_id else None,
            }
        )

    events.sort(key=lambda event: event["date"])
    return events


async def _run_document_agent(db: AsyncSession, input_data: dict[str, Any], *, user_id: UUID) -> dict[str, Any]:
    document = await db.get(Document, UUID(input_data["document_id"]))
    if document is None:
        raise ValueError("document not found")
    if document.status != "ready" or not document.ocr_text:
        raise ValueError(f"document is not ready yet (status: {document.status})")
    summary = await _generate_summary(db, document, user_id=user_id)
    return {"summary": summary}


async def _run_planner_agent(db: AsyncSession, input_data: dict[str, Any], *, user_id: UUID) -> dict[str, Any]:
    document = await db.get(Document, UUID(input_data["document_id"]))
    if document is None or not document.ocr_text:
        raise ValueError("document not found or has no OCR text yet")
    tasks = await extract_tasks(
        db, document_id=document.id, text=document.ocr_text, user_id=user_id, source="planner_agent"
    )
    return {"task_count": len(tasks)}


async def _run_entity_agent(db: AsyncSession, input_data: dict[str, Any], *, user_id: UUID) -> dict[str, Any]:
    document = await db.get(Document, UUID(input_data["document_id"]))
    if document is None or not document.ocr_text:
        raise ValueError("document not found or has no OCR text yet")
    entities = await extract_entities(db, document_id=document.id, text=document.ocr_text, user_id=user_id)
    return {"entity_count": len(entities)}


async def _run_legal_agent(db: AsyncSession, input_data: dict[str, Any], *, user_id: UUID) -> dict[str, Any]:
    document_ids = [UUID(doc_id) for doc_id in input_data.get("document_ids", [])]
    result = await _generate_draft(
        db, instruction=input_data["instruction"], user_id=user_id, document_ids=document_ids
    )
    return {"draft": result.draft, "citation_count": len(result.citations)}


async def _run_collection_agent(db: AsyncSession, input_data: dict[str, Any], *, user_id: UUID) -> dict[str, Any]:
    document_ids = [UUID(doc_id) for doc_id in input_data["document_ids"]]
    return await organize_document_collection(db, document_ids)


async def _run_timeline_agent(db: AsyncSession, input_data: dict[str, Any], *, user_id: UUID) -> dict[str, Any]:
    document_ids = [UUID(doc_id) for doc_id in input_data["document_ids"]]
    return {"timeline": await generate_timeline(db, document_ids)}


AGENT_DISPATCH = {
    "document_agent": _run_document_agent,
    "planner_agent": _run_planner_agent,
    "entity_agent": _run_entity_agent,
    "legal_agent": _run_legal_agent,
    "collection_agent": _run_collection_agent,
    "timeline_agent": _run_timeline_agent,
}


async def create_plan(db: AsyncSession, *, user_id: UUID, goal_type: str, goal_params: dict[str, Any]) -> Plan:
    if goal_type not in GOAL_TYPES:
        raise ValueError(f"unknown goal_type: {goal_type!r}")

    step_specs = build_steps(goal_type, goal_params)
    # Not wrapped in try/except: approval gating is security-relevant, so a
    # lookup failure should fail create_plan() loudly rather than silently
    # falling back to a possibly-wrong default (ADR 0029).
    approval_required_goals = await get_approval_required_goals(db, user_id, default=APPROVAL_REQUIRED_GOALS)
    requires_approval = goal_type in approval_required_goals

    plan = Plan(
        user_id=user_id,
        goal_type=goal_type,
        goal_params=goal_params,
        requires_approval=requires_approval,
        status="pending_approval" if requires_approval else "running",
    )
    db.add(plan)
    await db.flush()

    for index, spec in enumerate(step_specs):
        db.add(PlanStep(plan_id=plan.id, step_index=index, agent=spec["agent"], input_data=spec["input_data"]))

    await db.commit()
    await db.refresh(plan)
    return plan


async def approve_plan(db: AsyncSession, *, plan_id: UUID, user_id: UUID, is_admin: bool = False) -> Plan | None:
    plan = await db.get(Plan, plan_id)
    if plan is None or (plan.user_id != user_id and not is_admin):
        return None
    if not plan.requires_approval or plan.status != "pending_approval":
        return plan

    plan.status = "running"
    plan.approved_at = datetime.now(timezone.utc)
    await db.commit()

    await execute_plan(db, plan_id=plan.id)
    await db.refresh(plan)

    try:
        await create_decision_from_plan(db, plan=plan, user_id=user_id)
    except Exception:  # noqa: BLE001 - recording the decision must never fail the approval that already happened
        logger.exception("failed to record Decision for approved plan %s", plan.id)

    return plan


async def execute_plan(db: AsyncSession, *, plan_id: UUID) -> None:
    """Run every step of a plan in order. A step that keeps failing is isolated, not fatal to the plan."""
    plan = await db.get(Plan, plan_id)
    if plan is None:
        return

    steps_result = await db.execute(select(PlanStep).where(PlanStep.plan_id == plan_id).order_by(PlanStep.step_index))
    steps = list(steps_result.scalars().all())

    any_done = False
    any_failed = False
    for step in steps:
        step.status = "running"
        step.started_at = datetime.now(timezone.utc)
        await db.commit()

        handler = AGENT_DISPATCH[step.agent]
        result: dict[str, Any] | None = None
        error: str | None = None
        for attempt in range(MAX_STEP_ATTEMPTS):
            try:
                result = await handler(db, step.input_data, user_id=plan.user_id)
                error = None
                break
            except Exception as exc:  # noqa: BLE001 - a failing step must not abort the rest of the plan
                error = str(exc)[:2000]
                logger.warning(
                    "plan step %s (%s) failed on attempt %d/%d: %s",
                    step.id, step.agent, attempt + 1, MAX_STEP_ATTEMPTS, error,
                )

        step.completed_at = datetime.now(timezone.utc)
        if error is None:
            step.status = "done"
            step.result_data = result
            any_done = True
        else:
            step.status = "failed"
            step.error = error
            any_failed = True
        await db.commit()

    plan.completed_at = datetime.now(timezone.utc)
    if any_failed and any_done:
        plan.status = "partially_failed"
    elif any_failed:
        plan.status = "failed"
    else:
        plan.status = "completed"
    await db.commit()
