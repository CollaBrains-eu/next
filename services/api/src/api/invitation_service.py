"""Org invitations by email (Priority 3 commercial SaaS, ADR 0074).

Distinct from the pre-existing case/workspace sharing (cases_router.py,
workspace_router.py), which both require the invitee to already be a
provisioned platform user -- this works for a stranger who has never
signed up, by carrying its token through registration_service if needed
(see PendingRegistration.invitation_token).
"""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.email_client import send_email
from api.models import Invitation, User

TOKEN_TTL_DAYS = 7


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


async def is_already_a_member(db: AsyncSession, *, organization_id: UUID, email: str) -> bool:
    result = await db.execute(
        select(User).where(User.organization_id == organization_id, User.email == email)
    )
    return result.scalar_one_or_none() is not None


async def get_pending_invitation_for_email(
    db: AsyncSession, *, organization_id: UUID, email: str
) -> Invitation | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Invitation).where(
            Invitation.organization_id == organization_id,
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def create_invitation(
    db: AsyncSession, *, organization_id: UUID, email: str, invited_by_user_id: UUID
) -> Invitation:
    invitation = Invitation(
        organization_id=organization_id,
        email=email,
        invited_by_user_id=invited_by_user_id,
        token=_generate_token(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def refresh_invitation(db: AsyncSession, *, invitation: Invitation) -> Invitation:
    """A second invite to the same still-pending email is treated as
    "resend", not a duplicate -- same reasoning as
    registration_service.refresh_pending_registration."""
    invitation.token = _generate_token()
    invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS)
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def get_valid_invitation(db: AsyncSession, *, token: str) -> Invitation | None:
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    invitation = result.scalar_one_or_none()
    if invitation is None or invitation.accepted_at is not None or invitation.revoked_at is not None:
        return None
    if invitation.expires_at < datetime.now(timezone.utc):
        return None
    return invitation


async def list_pending_invitations(db: AsyncSession, *, organization_id: UUID) -> list[Invitation]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Invitation)
        .where(
            Invitation.organization_id == organization_id,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at > now,
        )
        .order_by(Invitation.created_at)
    )
    return list(result.scalars().all())


async def revoke_invitation(db: AsyncSession, *, invitation_id: UUID, organization_id: UUID) -> Invitation | None:
    invitation = await db.get(Invitation, invitation_id)
    if invitation is None or invitation.organization_id != organization_id:
        return None
    invitation.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def accept_invitation_for_existing_user(db: AsyncSession, *, token: str, user: User) -> Invitation | None:
    """The invitee already has an account and is logged in -- switches
    their membership straight into the inviting org. A user belongs to
    exactly one org (Organization's own docstring documents this
    constraint), so accepting an invitation always means leaving
    whichever org they were in before."""
    invitation = await get_valid_invitation(db, token=token)
    if invitation is None:
        return None
    user.organization_id = invitation.organization_id
    invitation.accepted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invitation)
    return invitation


def _invitation_text(*, organization_name: str, accept_url: str) -> str:
    return (
        f"Je bent uitgenodigd om je aan te sluiten bij {organization_name} op CollaBrains.\n\n"
        f"Klik op onderstaande link om de uitnodiging te accepteren:\n{accept_url}\n\n"
        "Deze link is 7 dagen geldig.\n\n"
        "Met vriendelijke groet,\nCollaBrains"
    )


def _invitation_html(*, organization_name: str, accept_url: str) -> str:
    return (
        f"<p>Je bent uitgenodigd om je aan te sluiten bij <strong>{organization_name}</strong> op CollaBrains.</p>"
        f'<p><a href="{accept_url}">{accept_url}</a></p>'
        "<p>Deze link is 7 dagen geldig.</p>"
        "<p>Met vriendelijke groet,<br>CollaBrains</p>"
    )


async def send_invitation_email(*, invitation: Invitation, organization_name: str) -> bool:
    accept_url = f"{settings.app_base_url}/invitations/{invitation.token}"
    return await send_email(
        to_address=invitation.email,
        subject=f"Uitnodiging voor {organization_name} op CollaBrains",
        html_body=_invitation_html(organization_name=organization_name, accept_url=accept_url),
        text_body=_invitation_text(organization_name=organization_name, accept_url=accept_url),
    )
