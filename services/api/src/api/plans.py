"""Planning Engine endpoints (Phase 8c, ADR 0019)."""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import async_session, get_db
from api.models import Plan, PlanStep, User
from api.planning_engine import GOAL_TYPES, approve_plan, create_plan, execute_plan

router = APIRouter(tags=["plans"])


class PlanCreateRequest(BaseModel):
    goal_type: str
    goal_params: dict[str, Any] = {}


class PlanStepOut(BaseModel):
    id: UUID
    step_index: int
    agent: str
    status: str
    result_data: dict[str, Any] | None
    error: str | None


class PlanOut(BaseModel):
    id: UUID
    goal_type: str
    goal_params: dict[str, Any]
    status: str
    requires_approval: bool
    created_at: datetime
    approved_at: datetime | None
    completed_at: datetime | None
    steps: list[PlanStepOut]


async def _to_plan_out(db: AsyncSession, plan: Plan) -> PlanOut:
    steps_result = await db.execute(select(PlanStep).where(PlanStep.plan_id == plan.id).order_by(PlanStep.step_index))
    steps = list(steps_result.scalars().all())
    return PlanOut(
        id=plan.id,
        goal_type=plan.goal_type,
        goal_params=plan.goal_params,
        status=plan.status,
        requires_approval=plan.requires_approval,
        created_at=plan.created_at,
        approved_at=plan.approved_at,
        completed_at=plan.completed_at,
        steps=[
            PlanStepOut(
                id=step.id, step_index=step.step_index, agent=step.agent, status=step.status,
                result_data=step.result_data, error=step.error,
            )
            for step in steps
        ],
    )


async def _run_plan_in_background(plan_id: UUID) -> None:
    async with async_session() as db:
        await execute_plan(db, plan_id=plan_id)


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan_endpoint(
    request: PlanCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlanOut:
    if request.goal_type not in GOAL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown goal_type: {request.goal_type!r}"
        )

    try:
        plan = await create_plan(
            db, user_id=current_user.id, goal_type=request.goal_type, goal_params=request.goal_params
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not plan.requires_approval:
        background_tasks.add_task(_run_plan_in_background, plan.id)

    return await _to_plan_out(db, plan)


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlanOut]:
    result = await db.execute(select(Plan).where(Plan.user_id == current_user.id).order_by(Plan.created_at.desc()))
    plans = list(result.scalars().all())
    return [await _to_plan_out(db, plan) for plan in plans]


@router.get("/plans/{plan_id}", response_model=PlanOut)
async def get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlanOut:
    plan = await db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return await _to_plan_out(db, plan)


@router.post("/plans/{plan_id}/approve", response_model=PlanOut)
async def approve_plan_endpoint(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlanOut:
    plan = await approve_plan(
        db, plan_id=plan_id, user_id=current_user.id, is_admin=current_user.role == "admin"
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return await _to_plan_out(db, plan)
