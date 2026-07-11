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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.admin_service import (
    AdminStats,
    AiUsageRow,
    ServiceHealth,
    analyze_bug_report,
    create_bug_report,
    get_admin_stats,
    get_ai_usage_report,
    get_service_health,
    list_bug_reports,
)
from api.auth import get_current_user, validate_phone_number
from api.db import get_db
from api.ldap_auth import LdapAdminError
from api.ldap_auth import create_user as ldap_create_user
from api.models import BugReport, PendingUserPhoneNumber, User

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

    class Config:
        from_attributes = True


class BugReportCreate(BaseModel):
    description: str


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
