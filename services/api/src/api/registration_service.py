"""Self-service signup (Priority 3 commercial SaaS, ADR 0074).

Distinct from onboarding_service.py, which emails an *already-provisioned*
LDAP/Postgres user their first link -- here, no LDAP entry or Postgres
`User` row exists yet. A `PendingRegistration` row holds everything needed
to create one, gated behind clicking an emailed verification link, so an
email address is confirmed reachable before any account (and its own new
Organization) is provisioned.
"""
import secrets
from datetime import datetime, timedelta, timezone

from ldap3 import HASHED_SALTED_SHA
from ldap3.utils.hashed import hashed
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.email_client import send_email
from api.ldap_auth import LdapAdminError
from api.ldap_auth import register_user as ldap_register_user
from api.models import Organization, PendingRegistration, User

TOKEN_TTL_HOURS = 24

_redis = Redis.from_url(settings.redis_url)


def hash_password(password: str) -> str:
    return hashed(HASHED_SALTED_SHA, password)


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


async def check_registration_rate_limit(email: str) -> bool:
    """Fixed-window limiter keyed by email (same pattern as
    ai_gateway._check_rate_limit) -- bounds how many verification emails
    one address can be sent per hour. Returns False when the limit is
    exceeded; the router turns that into a 429."""
    key = f"registration_rate_limit:{email}"
    count = await _redis.incr(key)
    if count == 1:
        await _redis.expire(key, 3600)
    return count <= settings.registration_rate_limit_per_hour


async def username_or_email_taken(db: AsyncSession, *, username: str, email: str) -> str | None:
    """Returns "username_taken"/"email_taken", or None if both are free.
    Checks confirmed Users plus any still-valid (unexpired, unconsumed)
    pending registration -- an expired or already-consumed row doesn't
    block a retry."""
    existing_user = await db.execute(select(User).where(User.username == username))
    if existing_user.scalar_one_or_none() is not None:
        return "username_taken"

    now = datetime.now(timezone.utc)
    existing_pending = await db.execute(
        select(PendingRegistration).where(
            PendingRegistration.username == username,
            PendingRegistration.consumed_at.is_(None),
            PendingRegistration.expires_at > now,
        )
    )
    if existing_pending.scalar_one_or_none() is not None:
        return "username_taken"

    existing_email = await db.execute(select(User).where(User.email == email))
    if existing_email.scalar_one_or_none() is not None:
        return "email_taken"

    return None


async def get_pending_registration_for_username(db: AsyncSession, *, username: str) -> PendingRegistration | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PendingRegistration).where(
            PendingRegistration.username == username,
            PendingRegistration.consumed_at.is_(None),
            PendingRegistration.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def create_pending_registration(
    db: AsyncSession,
    *,
    username: str,
    display_name: str,
    email: str,
    password: str,
    organization_name: str,
    invitation_token: str | None = None,
) -> PendingRegistration:
    record = PendingRegistration(
        username=username,
        display_name=display_name,
        email=email,
        password_hash=hash_password(password),
        organization_name=organization_name,
        invitation_token=invitation_token,
        token=_generate_token(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def refresh_pending_registration(
    db: AsyncSession,
    *,
    record: PendingRegistration,
    display_name: str,
    email: str,
    password: str,
    organization_name: str,
    invitation_token: str | None = None,
) -> PendingRegistration:
    """A second /auth/register call for a username that already has a
    still-valid pending registration is treated as "resend the
    verification email", not a conflict -- covers the very common case of
    the first email getting lost/delayed, without a separate
    resend-verification endpoint. Latest submitted details win and get a
    fresh token/expiry, since the user is re-typing this at signup time."""
    record.display_name = display_name
    record.email = email
    record.password_hash = hash_password(password)
    record.organization_name = organization_name
    record.invitation_token = invitation_token
    record.token = _generate_token()
    record.expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    await db.commit()
    await db.refresh(record)
    return record


async def get_valid_pending_registration(db: AsyncSession, *, token: str) -> PendingRegistration | None:
    result = await db.execute(select(PendingRegistration).where(PendingRegistration.token == token))
    record = result.scalar_one_or_none()
    if record is None or record.consumed_at is not None:
        return None
    if record.expires_at < datetime.now(timezone.utc):
        return None
    return record


async def complete_registration(db: AsyncSession, *, token: str) -> User | None:
    """Verifies the token, then creates the LDAP entry and the Postgres
    User row -- the point where a signup stops being "pending" and
    becomes a real account. Returns None if the registration token (or,
    for an invited signup, the invitation it carries) is invalid, expired,
    already used/accepted, or revoked; the router maps that to a 400.

    Two shapes, chosen by whether `record.invitation_token` is set
    (invitation_service, ADR 0074): an ordinary signup gets a brand-new
    Organization with itself as owner; an invited signup joins the
    inviting org instead and is never made its owner.
    """
    record = await get_valid_pending_registration(db, token=token)
    if record is None:
        return None

    invitation = None
    if record.invitation_token is not None:
        from api.invitation_service import get_valid_invitation

        invitation = await get_valid_invitation(db, token=record.invitation_token)
        if invitation is None:
            return None

    try:
        ldap_register_user(
            username=record.username,
            display_name=record.display_name,
            email=record.email,
            password_hash=record.password_hash,
        )
    except LdapAdminError as exc:
        if "already exists" not in str(exc).lower():
            raise
        # The directory entry was already created by a prior verify
        # attempt that crashed after the LDAP write but before the
        # Postgres commit below -- proceed rather than stranding the user
        # with a directory account they can never finish provisioning.

    organization = None
    if invitation is None:
        organization = Organization(name=record.organization_name)
        db.add(organization)
        await db.flush()
        organization_id = organization.id
    else:
        organization_id = invitation.organization_id

    # role stays the "member" default deliberately -- User.role is
    # platform-wide (see Organization.owner_user_id's docstring), so a
    # self-service signup must not grant platform admin. owner_user_id
    # below is what actually lets an (uninvited) registrant manage their
    # own new org; an invited signup gets neither.
    user = User(
        username=record.username,
        display_name=record.display_name,
        email=record.email,
        organization_id=organization_id,
    )
    db.add(user)
    await db.flush()

    if invitation is not None:
        invitation.accepted_at = datetime.now(timezone.utc)
    else:
        organization.owner_user_id = user.id

    record.consumed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


def _verification_text(*, display_name: str, verify_url: str) -> str:
    return (
        f"Hallo {display_name},\n\n"
        "Bevestig je e-mailadres om je CollaBrains-account te activeren:\n"
        f"{verify_url}\n\n"
        "Deze link is 24 uur geldig. Heb je dit niet aangevraagd? Negeer dan dit bericht.\n\n"
        "Met vriendelijke groet,\nCollaBrains"
    )


def _verification_html(*, display_name: str, verify_url: str) -> str:
    return (
        f"<p>Hallo {display_name},</p>"
        "<p>Bevestig je e-mailadres om je CollaBrains-account te activeren:</p>"
        f'<p><a href="{verify_url}">{verify_url}</a></p>'
        "<p>Deze link is 24 uur geldig. Heb je dit niet aangevraagd? Negeer dan dit bericht.</p>"
        "<p>Met vriendelijke groet,<br>CollaBrains</p>"
    )


async def send_verification_email(*, registration: PendingRegistration) -> bool:
    verify_url = f"{settings.app_base_url}/verify-email?token={registration.token}"
    return await send_email(
        to_address=registration.email,
        subject="Bevestig je CollaBrains-account",
        html_body=_verification_html(display_name=registration.display_name, verify_url=verify_url),
        text_body=_verification_text(display_name=registration.display_name, verify_url=verify_url),
    )
