"""Knowledge Graph 2: Decision nodes and generalized cross-type edges
(Phase 10, ADR 0025).

`create_decision_from_plan` is a side effect of approving a Plan
(api.planning_engine.approve_plan) -- it must never fail the approval
itself, callers are expected to wrap it the same way every other side
effect in this codebase is (Signal notifications, memory
retrieval/creation, reflection).
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Decision, Document, GraphEdge, Plan


async def create_decision_from_plan(db: AsyncSession, *, plan: Plan, user_id: UUID) -> Decision:
    """Record a Decision for an approved plan, linked to its referenced documents.

    `derived_from` edges point from the Decision to each Document in
    `plan.goal_params["document_ids"]` -- the evidence the decision was
    based on.
    """
    decision = Decision(user_id=user_id, plan_id=plan.id, summary=f"Approved {plan.goal_type} (plan {plan.id})")
    db.add(decision)
    await db.flush()

    document_ids = plan.goal_params.get("document_ids") or []
    for document_id in document_ids:
        db.add(
            GraphEdge(
                source_type="decision",
                source_id=decision.id,
                target_type="document",
                target_id=UUID(document_id) if isinstance(document_id, str) else document_id,
                relationship_type="derived_from",
            )
        )

    await db.commit()
    await db.refresh(decision)
    return decision


async def get_decision_with_documents(db: AsyncSession, decision_id: UUID) -> tuple[Decision, list[Document]] | None:
    """Answers "which documents support this decision?" (ADR 0025)."""
    decision = await db.get(Decision, decision_id)
    if decision is None:
        return None

    edges_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.source_type == "decision",
            GraphEdge.source_id == decision_id,
            GraphEdge.relationship_type == "derived_from",
            GraphEdge.target_type == "document",
        )
    )
    document_ids = [edge.target_id for edge in edges_result.scalars().all()]

    documents: list[Document] = []
    if document_ids:
        documents_result = await db.execute(select(Document).where(Document.id.in_(document_ids)))
        documents = list(documents_result.scalars().all())

    return decision, documents
