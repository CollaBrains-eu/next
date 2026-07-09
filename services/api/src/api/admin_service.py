"""Admin Dashboard aggregation queries and health checks (Phase 22).

Kept separate from `admin_router.py` so the aggregation logic is testable
without going through HTTP, same split as `documents.py`'s helpers vs.
`documents_router`. Reads existing data only -- `AiCallLog` (ADR 0003)
already has everything the AI-usage report needs, so this module adds no
new tracking, only reporting. See docs/superpowers/plans/2026-07-09-fase1-admin-dashboard.md.
"""
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.config import settings
from api.models import AiCallLog, BugReport, Document, User

ANALYSIS_PROMPT = (
    "You are triaging a bug report for an AI workspace platform. Given the report below, "
    "write a short (2-4 sentence) analysis: likely cause, affected area, and severity "
    "(low/medium/high). Do not invent details the report doesn't contain.\n\nReport: {description}"
)


class AdminStats(BaseModel):
    total_users: int
    total_documents: int
    documents_by_status: dict[str, int]
    ai_calls_last_24h: int


class AiUsageRow(BaseModel):
    key: str
    call_count: int
    total_prompt_tokens: int
    total_completion_tokens: int


class ServiceHealth(BaseModel):
    name: str
    status: Literal["up", "down"]
    detail: str | None = None


async def get_admin_stats(db: AsyncSession) -> AdminStats:
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_documents = (await db.execute(select(func.count()).select_from(Document))).scalar_one()

    status_rows = await db.execute(select(Document.status, func.count()).group_by(Document.status))
    documents_by_status = {status: count for status, count in status_rows.all()}

    cutoff = datetime.utcnow() - timedelta(hours=24)
    ai_calls_last_24h = (
        await db.execute(select(func.count()).select_from(AiCallLog).where(AiCallLog.created_at >= cutoff))
    ).scalar_one()

    return AdminStats(
        total_users=total_users,
        total_documents=total_documents,
        documents_by_status=documents_by_status,
        ai_calls_last_24h=ai_calls_last_24h,
    )


async def get_ai_usage_report(
    db: AsyncSession, *, since: datetime, group_by: Literal["user", "model", "endpoint"]
) -> list[AiUsageRow]:
    column = {"user": AiCallLog.user_id, "model": AiCallLog.model, "endpoint": AiCallLog.endpoint}[group_by]

    result = await db.execute(
        select(
            column,
            func.count().label("call_count"),
            func.coalesce(func.sum(AiCallLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(AiCallLog.completion_tokens), 0).label("completion_tokens"),
        )
        .where(AiCallLog.created_at >= since)
        .group_by(column)
    )

    return [
        AiUsageRow(
            key=str(key),
            call_count=call_count,
            total_prompt_tokens=prompt_tokens,
            total_completion_tokens=completion_tokens,
        )
        for key, call_count, prompt_tokens, completion_tokens in result.all()
    ]


async def _check_http_health(name: str, url: str) -> ServiceHealth:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
        if response.status_code < 500:
            return ServiceHealth(name=name, status="up")
        return ServiceHealth(name=name, status="down", detail=f"HTTP {response.status_code}")
    except Exception as exc:  # noqa: BLE001 - a health check must report every failure mode, never raise
        return ServiceHealth(name=name, status="down", detail=str(exc)[:200])


async def get_service_health(db: AsyncSession) -> list[ServiceHealth]:
    """Health of every service `services/api` depends on.

    Deliberately reuses no per-service health-check module (v2 had one,
    `_paperless_health`/`_ollama_health`/etc.) -- with only 3 external
    dependencies today, one shared httpx-based checker plus a direct
    `SELECT 1` for Postgres is the smallest slice that covers them, same
    reasoning as every other "don't build a framework for 3 things"
    decision already in this codebase.
    """
    results: list[ServiceHealth] = []

    try:
        await db.execute(select(1))
        results.append(ServiceHealth(name="postgres", status="up"))
    except Exception as exc:  # noqa: BLE001 - health check must report, not raise
        results.append(ServiceHealth(name="postgres", status="down", detail=str(exc)[:200]))

    results.append(await _check_http_health("paperless", f"{settings.paperless_url}/api/"))
    results.append(await _check_http_health("ollama", f"{settings.ollama_url}/api/tags"))

    return results


async def list_bug_reports(db: AsyncSession, *, status: str | None = None) -> list[BugReport]:
    query = select(BugReport).order_by(BugReport.created_at.desc())
    if status is not None:
        query = query.where(BugReport.status == status)
    return list((await db.execute(query)).scalars().all())


async def create_bug_report(db: AsyncSession, *, user_id: UUID, description: str) -> BugReport:
    report = BugReport(user_id=user_id, description=description)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def analyze_bug_report(db: AsyncSession, *, bug_report_id: UUID, requesting_user_id: UUID) -> BugReport | None:
    report = await db.get(BugReport, bug_report_id)
    if report is None:
        return None

    prompt = ANALYSIS_PROMPT.format(description=report.description[:4000])
    analysis = await chat_completion(
        [{"role": "user", "content": prompt}], user_id=requesting_user_id, endpoint="admin.analyze_bug_report"
    )

    report.ai_analysis = analysis
    report.status = "analyzed"
    await db.commit()
    await db.refresh(report)
    return report
