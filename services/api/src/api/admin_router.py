"""Admin Dashboard endpoints (Phase 22).

admin-role-only throughout, same `_require_admin` pattern as
`organizations_router.py`. All read/report endpoints reuse existing data
(`AiCallLog`, `User`, `Document`) -- only the Bug Reports feature adds a
new table, migrated from CollaBrains v2's admin tab (v2 had no AI-usage
cost reporting to migrate; that part is new here since Next already had
the underlying `AiCallLog` audit trail v2 never built).
"""
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.admin_service import (
    AdminStats,
    AiUsageRow,
    AnalyzeAllStatus,
    CodebergIssueNotConfigured,
    ServiceHealth,
    analyze_all_is_running,
    analyze_bug_report,
    bulk_delete_bug_reports,
    create_bug_report,
    create_bug_report_from_text,
    create_codeberg_issue,
    delete_bug_report,
    find_user_by_phone,
    generate_clarifying_questions,
    get_admin_stats,
    get_ai_usage_report,
    get_analyze_all_status,
    get_service_health,
    get_service_health_by_name,
    get_service_logs,
    list_bug_reports,
    run_analyze_all,
    update_bug_report_status,
)
from api.auth import get_current_user, validate_phone_number
from api.onboarding_service import send_welcome
from api.config import settings
from api.db import get_db
from api.events import EventType, publish
from api.ldap_auth import LdapAdminError
from api.ldap_auth import create_user as ldap_create_user
from api.models import BugReport, Document, PendingUserPhoneNumber, User

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


class BugReportOut(BaseModel):
    id: UUID
    user_id: UUID
    description: str
    status: str
    ai_analysis: str | None
    created_at: datetime
    title: str | None = None
    page_url: str | None = None
    ai_labels: str | None = None
    ai_priority: str | None = None
    ai_suggested_fix: str | None = None
    codeberg_issue_url: str | None = None
    codeberg_issue_number: int | None = None
    clarifying_questions: str | None = None
    clarifying_answers: str | None = None
    clarifying_status: str | None = None

    class Config:
        from_attributes = True


class BugReportCreate(BaseModel):
    description: str


class BugReportStatusUpdate(BaseModel):
    status: str


class BugReportBulkDelete(BaseModel):
    ids: list[UUID]


class BugReportBulkDeleteOut(BaseModel):
    ok: bool = True
    deleted: int


class ClarifyOut(BaseModel):
    ok: bool = True
    questions: list[str]


class SignalLookupOut(BaseModel):
    id: UUID
    display_name: str


class SignalBugFromTextIn(BaseModel):
    text: str
    owner_uid: str


class SignalBugFromTextOut(BaseModel):
    ok: bool = True
    id: UUID


def _require_internal_secret(x_internal_secret: str | None) -> None:
    if not settings.internal_api_secret or x_internal_secret != settings.internal_api_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal secret")


class AdminUserCreate(BaseModel):
    username: str
    display_name: str
    email: str
    is_admin: bool = False
    phone_number: str | None = None


class AdminUserCreated(BaseModel):
    username: str
    temporary_password: str


class AdminUserOut(BaseModel):
    id: UUID
    username: str
    display_name: str
    email: str | None
    role: str
    phone_number: str | None
    created_at: datetime
    last_login_at: datetime | None

    class Config:
        from_attributes = True


@router.get("/stats", response_model=AdminStats)
async def admin_stats(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> AdminStats:
    _require_admin(current_user)
    return await get_admin_stats(db)


@router.get("/ai-usage", response_model=list[AiUsageRow])
async def admin_ai_usage(
    group_by: Literal["user", "model", "endpoint"] = "model",
    since_hours: int = 24 * 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AiUsageRow]:
    _require_admin(current_user)
    since = datetime.utcnow() - timedelta(hours=since_hours)
    return await get_ai_usage_report(db, since=since, group_by=group_by)


@router.get("/health", response_model=list[ServiceHealth])
async def admin_health(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[ServiceHealth]:
    _require_admin(current_user)
    return await get_service_health(db)


@router.get("/health/service/{name}", response_model=ServiceHealth)
async def admin_health_service(
    name: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ServiceHealth:
    _require_admin(current_user)
    health = await get_service_health_by_name(db, name)
    if health is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown service")
    return health


@router.get("/services/{name}/logs")
async def admin_service_logs(
    name: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    _require_admin(current_user)
    logs = await get_service_logs(db, name)
    if logs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown service")
    return logs


@router.get("/bug-reports", response_model=list[BugReportOut])
async def admin_list_bug_reports(
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BugReport]:
    _require_admin(current_user)
    return await list_bug_reports(db, status=status_filter)


@router.post("/bug-reports", response_model=BugReportOut)
async def admin_create_bug_report(
    body: BugReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugReport:
    # Deliberately not admin-only -- any authenticated user can report a bug,
    # only *reading*/*analyzing* the queue is admin-gated.
    return await create_bug_report(db, user_id=current_user.id, description=body.description)


@router.post("/bug-reports/{bug_report_id}/analyze", response_model=BugReportOut)
async def admin_analyze_bug_report(
    bug_report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugReport:
    _require_admin(current_user)
    report = await analyze_bug_report(db, bug_report_id=bug_report_id, requesting_user_id=current_user.id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug report not found")
    return report


@router.put("/bug-reports/{bug_report_id}/status", response_model=BugReportOut)
async def admin_update_bug_report_status(
    bug_report_id: UUID,
    body: BugReportStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugReport:
    _require_admin(current_user)
    report = await update_bug_report_status(db, bug_report_id=bug_report_id, status=body.status)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug report not found")
    return report


@router.delete("/bug-reports", response_model=BugReportBulkDeleteOut)
async def admin_bulk_delete_bug_reports(
    body: BugReportBulkDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugReportBulkDeleteOut:
    _require_admin(current_user)
    deleted = await bulk_delete_bug_reports(db, ids=body.ids)
    return BugReportBulkDeleteOut(deleted=deleted)


@router.delete("/bug-reports/{bug_report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_bug_report(
    bug_report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    deleted = await delete_bug_report(db, bug_report_id=bug_report_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug report not found")


@router.post("/bug-reports/analyze-all")
async def admin_analyze_all_bug_reports(
    background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)
) -> dict:
    _require_admin(current_user)
    if analyze_all_is_running():
        status_snapshot = get_analyze_all_status()
        return {"ok": False, "detail": "Already running", **status_snapshot.model_dump()}
    background_tasks.add_task(run_analyze_all)
    return {"ok": True, "started": True}


@router.get("/bug-reports/analyze-all/status", response_model=AnalyzeAllStatus)
async def admin_analyze_all_bug_reports_status(current_user: User = Depends(get_current_user)) -> AnalyzeAllStatus:
    _require_admin(current_user)
    return get_analyze_all_status()


@router.post("/bug-reports/{bug_report_id}/clarify", response_model=ClarifyOut)
async def admin_clarify_bug_report(
    bug_report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClarifyOut:
    _require_admin(current_user)
    result = await generate_clarifying_questions(
        db, bug_report_id=bug_report_id, requesting_user_id=current_user.id
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug report not found")
    _report, questions = result
    if not questions:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No clarifying questions generated")
    return ClarifyOut(questions=questions)


class CodebergIssueOut(BaseModel):
    ok: bool = True
    url: str
    number: int


@router.post("/bug-reports/{bug_report_id}/codeberg-issue", response_model=CodebergIssueOut)
async def admin_create_codeberg_issue(
    bug_report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CodebergIssueOut:
    _require_admin(current_user)
    try:
        report = await create_codeberg_issue(db, bug_report_id=bug_report_id)
    except CodebergIssueNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Codeberg integration is not configured"
        ) from exc
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug report not found")
    return CodebergIssueOut(url=report.codeberg_issue_url, number=report.codeberg_issue_number)


@router.post("/users", response_model=AdminUserCreated)
async def admin_create_user(
    body: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdminUserCreated:
    """Create a new LDAP user with a one-time temporary password. The
    Postgres User row is not created here -- it appears on first login,
    same auto-provision path as every other user. If a phone number was
    given, it's staged in `pending_user_phone_numbers` and consumed by
    `_get_or_provision_user` (auth.py) the moment that row is created."""
    _require_admin(current_user)
    try:
        created = ldap_create_user(
            username=body.username, display_name=body.display_name, email=body.email, is_admin=body.is_admin,
        )
    except LdapAdminError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_409_CONFLICT if "already exists" in detail.lower() else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc

    if body.phone_number:
        phone = validate_phone_number(body.phone_number)
        existing = await db.execute(select(User).where(User.phone_number == phone))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This phone number is already linked to another account",
            )
        db.add(PendingUserPhoneNumber(username=body.username, phone_number=phone))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This phone number is already linked to another account",
            )

    return AdminUserCreated(username=created.username, temporary_password=created.temporary_password)


class DocumentReprocessOut(BaseModel):
    status: str


@router.post("/documents/{document_id}/reprocess", response_model=DocumentReprocessOut, status_code=status.HTTP_202_ACCEPTED)
async def admin_reprocess_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentReprocessOut:
    """Force-retry a document stuck or failed after upload (Phase 25). No
    credentials/LDAP writes involved -- re-runs the same OCR/embedding/
    extraction pipeline a first-time upload runs, using the bytes Paperless
    already has, so an admin doesn't have to ask the owner to re-upload
    after a transient Ollama/Paperless outage."""
    _require_admin(current_user)
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.paperless_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document has no stored source to reprocess from; it must be re-uploaded",
        )
    if document.status == "ready":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document already processed successfully")

    await publish(EventType.DOCUMENT_REPROCESS_REQUESTED, {"document_id": document_id})
    return DocumentReprocessOut(status="reprocess_queued")


@router.get("/users", response_model=list[AdminUserOut])
async def admin_list_users(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    _require_admin(current_user)
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/signal-lookup", response_model=SignalLookupOut)
async def admin_signal_lookup(
    phone: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> SignalLookupOut:
    """Resolve a phone number to a user (v2 scanned LDAP for a mobile-attr
    match; here phone_number is a direct indexed column on `users`)."""
    _require_admin(current_user)
    user = await find_user_by_phone(db, phone=phone)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user with this phone number")
    return SignalLookupOut(id=user.id, display_name=user.display_name)


@router.get("/signal-lookup-internal", response_model=SignalLookupOut)
async def admin_signal_lookup_internal(
    phone: str,
    db: AsyncSession = Depends(get_db),
    x_internal_secret: str | None = Header(None, alias="X-Internal-Secret"),
) -> SignalLookupOut:
    """Same lookup as /signal-lookup, but gated by a shared secret instead
    of an admin JWT -- for the Signal-ingest service to call directly."""
    _require_internal_secret(x_internal_secret)
    user = await find_user_by_phone(db, phone=phone)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user with this phone number")
    return SignalLookupOut(id=user.id, display_name=user.display_name)


@router.post("/signal/bug-from-text", response_model=SignalBugFromTextOut)
async def admin_signal_bug_from_text(
    body: SignalBugFromTextIn,
    db: AsyncSession = Depends(get_db),
    x_internal_secret: str | None = Header(None, alias="X-Internal-Secret"),
) -> SignalBugFromTextOut:
    """Create a bug report from Signal-ingested text (a user texting a bug
    report instead of using the web UI). Internal-secret-gated, same as
    /signal-lookup-internal."""
    _require_internal_secret(x_internal_secret)
    report = await create_bug_report_from_text(db, username=body.owner_uid, text=body.text)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown owner_uid")
    return SignalBugFromTextOut(id=report.id)


class ResendWelcomeOut(BaseModel):
    ok: bool = True
    email_sent: bool


@router.post("/users/{user_id}/resend-welcome", response_model=ResendWelcomeOut)
async def admin_resend_welcome(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResendWelcomeOut:
    """Send (or resend) a welcome/onboarding link to a user -- a fresh
    single-use token, emailed and Signal-messaged (best-effort, same
    contract as email_client.py/signal_client.py: no configured
    SMTP/Signal just means that channel silently doesn't fire)."""
    _require_admin(current_user)
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    email_sent = await send_welcome(db, user=user)
    return ResendWelcomeOut(email_sent=email_sent)
