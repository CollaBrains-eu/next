"""Admin Dashboard aggregation queries and health checks (Phase 22).

Kept separate from `admin_router.py` so the aggregation logic is testable
without going through HTTP, same split as `documents.py`'s helpers vs.
`documents_router`. Reads existing data only -- `AiCallLog` (ADR 0003)
already has everything the AI-usage report needs, so this module adds no
new tracking, only reporting. See docs/superpowers/plans/2026-07-09-fase1-admin-dashboard.md.
"""
import json
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.config import settings
from api.db import async_session
from api.models import AiCallLog, BugReport, Document, User

ANALYSIS_PROMPT = (
    "You are triaging a bug report for an AI workspace platform. Given the report below, "
    "write a short (2-4 sentence) analysis: likely cause, affected area, and severity "
    "(low/medium/high). Do not invent details the report doesn't contain.\n\nReport: {description}"
)

CLARIFY_PROMPT = (
    "You are triaging a bug report for an AI workspace platform. The report below is missing "
    "detail needed to act on it. Write 1-4 short, specific clarifying questions to ask the "
    "reporter. Respond with a JSON object: {{\"questions\": [\"...\", ...]}}. If the report "
    "already has enough detail, respond with {{\"questions\": []}}.\n\n"
    "Title: {title}\nPage: {page_url}\nDescription: {description}"
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


async def get_service_health_by_name(db: AsyncSession, name: str) -> ServiceHealth | None:
    """Health of a single named service (v2's `GET /admin/health/service/{name}`).

    None means "unknown service name" -- the router turns that into a 404.
    """
    if name == "postgres":
        try:
            await db.execute(select(1))
            return ServiceHealth(name="postgres", status="up")
        except Exception as exc:  # noqa: BLE001 - health check must report, not raise
            return ServiceHealth(name="postgres", status="down", detail=str(exc)[:200])
    if name == "paperless":
        return await _check_http_health("paperless", f"{settings.paperless_url}/api/")
    if name == "ollama":
        return await _check_http_health("ollama", f"{settings.ollama_url}/api/tags")
    return None


async def get_service_logs(db: AsyncSession, name: str) -> dict | None:
    """Per-service detail dump (v2's `GET /admin/services/{name}/logs`), a
    narrower subset than v2's 8 services -- limited to what this backend
    actually depends on (see get_service_health's docstring)."""
    if name == "database":
        documents = (await db.execute(select(func.count()).select_from(Document))).scalar_one()
        users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        bug_reports = (await db.execute(select(func.count()).select_from(BugReport))).scalar_one()
        return {"documents": documents, "users": users, "bug_reports": bug_reports}

    if name == "paperless":
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{settings.paperless_url}/api/documents/",
                    params={"ordering": "-modified", "page_size": 1},
                    auth=(settings.paperless_admin_user, settings.paperless_admin_password),
                )
            response.raise_for_status()
            body = response.json()
            results = body.get("results") or []
            last_updated = results[0].get("modified") if results else None
            return {"count": body.get("count", 0), "last_updated": last_updated}
        except Exception as exc:  # noqa: BLE001 - report failure in the payload, don't raise
            return {"count": None, "last_updated": None, "error": str(exc)[:200]}

    if name == "ollama":
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.ollama_url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            return {
                "models": [
                    {"name": m.get("name"), "size": m.get("size"), "modified_at": m.get("modified_at")}
                    for m in models
                ],
                "model_count": len(models),
            }
        except Exception as exc:  # noqa: BLE001 - report failure in the payload, don't raise
            return {"models": [], "model_count": 0, "error": str(exc)[:200]}

    return None


async def update_bug_report_status(db: AsyncSession, *, bug_report_id: UUID, status: str) -> BugReport | None:
    report = await db.get(BugReport, bug_report_id)
    if report is None:
        return None
    report.status = status
    await db.commit()
    await db.refresh(report)
    return report


async def delete_bug_report(db: AsyncSession, *, bug_report_id: UUID) -> bool:
    report = await db.get(BugReport, bug_report_id)
    if report is None:
        return False
    await db.delete(report)
    await db.commit()
    return True


async def bulk_delete_bug_reports(db: AsyncSession, *, ids: list[UUID]) -> int:
    deleted = 0
    for report_id in ids:
        report = await db.get(BugReport, report_id)
        if report is not None:
            await db.delete(report)
            deleted += 1
    await db.commit()
    return deleted


async def generate_clarifying_questions(
    db: AsyncSession, *, bug_report_id: UUID, requesting_user_id: UUID
) -> tuple[BugReport, list[str]] | None:
    report = await db.get(BugReport, bug_report_id)
    if report is None:
        return None

    prompt = CLARIFY_PROMPT.format(
        title=report.title or "", page_url=report.page_url or "", description=report.description[:4000]
    )
    raw = await chat_completion(
        [{"role": "user", "content": prompt}],
        user_id=requesting_user_id,
        endpoint="admin.clarify_bug_report",
        json_mode=True,
    )
    try:
        questions = json.loads(raw).get("questions", [])
    except (json.JSONDecodeError, AttributeError):
        questions = []

    report.clarifying_questions = json.dumps(questions)
    report.clarifying_answers = "{}"
    report.clarifying_status = "pending"
    await db.commit()
    await db.refresh(report)
    return report, questions


class AnalyzeAllStatus(BaseModel):
    running: bool
    done: int
    total: int
    errors: int


_analyze_all_status: dict = {"running": False, "done": 0, "total": 0, "errors": 0}


def get_analyze_all_status() -> AnalyzeAllStatus:
    return AnalyzeAllStatus(**_analyze_all_status)


def analyze_all_is_running() -> bool:
    return _analyze_all_status["running"]


async def run_analyze_all() -> None:
    """Background task: AI-analyze every not-yet-analyzed bug report.

    Uses its own session (not the request-scoped one) since it outlives the
    HTTP request that triggered it -- same reasoning as the event handlers
    in documents.py that open `async_session()` directly.
    """
    _analyze_all_status.update(running=True, done=0, total=0, errors=0)
    try:
        async with async_session() as db:
            result = await db.execute(select(BugReport).where(BugReport.ai_analysis.is_(None)))
            reports = list(result.scalars().all())
            _analyze_all_status["total"] = len(reports)
            for report in reports:
                try:
                    prompt = ANALYSIS_PROMPT.format(description=report.description[:4000])
                    report.ai_analysis = await chat_completion(
                        [{"role": "user", "content": prompt}],
                        user_id=report.user_id,
                        endpoint="admin.analyze_all_bug_reports",
                    )
                    report.status = "analyzed"
                    await db.commit()
                except Exception:  # noqa: BLE001 - one bad report shouldn't stop the batch
                    await db.rollback()
                    _analyze_all_status["errors"] += 1
                finally:
                    _analyze_all_status["done"] += 1
    finally:
        _analyze_all_status["running"] = False


class CodebergIssueNotConfigured(Exception):
    pass


async def create_codeberg_issue(db: AsyncSession, *, bug_report_id: UUID) -> BugReport | None:
    report = await db.get(BugReport, bug_report_id)
    if report is None:
        return None
    if report.codeberg_issue_url:
        return report
    if not settings.codeberg_api_token or not settings.codeberg_repo:
        raise CodebergIssueNotConfigured()

    title = report.title or report.description[:80]
    body_parts = [report.description]
    if report.ai_suggested_fix:
        body_parts.append(f"\n**Suggested fix:**\n{report.ai_suggested_fix}")
    if report.page_url:
        body_parts.append(f"\n**Page:** {report.page_url}")
    body = "\n".join(body_parts)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"https://codeberg.org/api/v1/repos/{settings.codeberg_repo}/issues",
            headers={"Authorization": f"token {settings.codeberg_api_token}"},
            json={"title": title, "body": body},
        )
    response.raise_for_status()
    issue = response.json()

    report.codeberg_issue_url = issue["html_url"]
    report.codeberg_issue_number = issue["number"]
    report.status = "in_behandeling"
    await db.commit()
    await db.refresh(report)
    return report


async def find_user_by_phone(db: AsyncSession, *, phone: str) -> User | None:
    result = await db.execute(select(User).where(User.phone_number == phone))
    return result.scalar_one_or_none()


async def create_bug_report_from_text(db: AsyncSession, *, username: str, text: str) -> BugReport | None:
    result = await db.execute(select(User).where(User.username == username))
    owner = result.scalar_one_or_none()
    if owner is None:
        return None

    report = BugReport(
        user_id=owner.id,
        title=text[:200],
        description=text,
        page_url="signal",
        status="open",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


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
