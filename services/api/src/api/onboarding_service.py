"""Welcome/onboarding email + Signal notification (Phase 27, v2 port).

Narrower than v2's onboarding: no PocketID one-time-token fallback (no
PocketID/OIDC layer exists here), no Signal-safety-number identity
verification (a separate, much larger feature). What's here: a
single-use token with an expiry, emailed (and Signal-messaged, if the
user has a phone number on file) as a link -- both channels best-effort,
matching email_client.py/signal_client.py's own contract.
"""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.email_client import send_email
from api.email_templates import onboarding_welcome_html, onboarding_welcome_subject, onboarding_welcome_text
from api.models import OnboardingToken, User
from api.preferences import get_preferences
from api.signal_client import send_signal_message

TOKEN_TTL_DAYS = 7


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


async def create_onboarding_token(db: AsyncSession, *, user_id: UUID) -> OnboardingToken:
    token = OnboardingToken(
        token=_generate_token(),
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


async def get_valid_onboarding_token(db: AsyncSession, *, token: str) -> OnboardingToken | None:
    result = await db.execute(select(OnboardingToken).where(OnboardingToken.token == token))
    record = result.scalar_one_or_none()
    if record is None:
        return None
    if record.used_at is not None:
        return None
    if record.expires_at < datetime.now(timezone.utc):
        return None
    return record


async def consume_onboarding_token(db: AsyncSession, *, token: str) -> OnboardingToken | None:
    record = await get_valid_onboarding_token(db, token=token)
    if record is None:
        return None
    record.used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return record


async def send_welcome(db: AsyncSession, *, user: User) -> bool:
    """Creates a fresh onboarding token and sends it via email (if the
    user has one) and Signal (if they have a phone number). Returns
    whether the email specifically was sent -- the admin endpoint uses
    this to report back "did the email actually go out"."""
    token = await create_onboarding_token(db, user_id=user.id)
    onboard_url = f"{settings.app_base_url}/onboard?token={token.token}"

    email_sent = False
    if user.email:
        preferences = await get_preferences(db, user_id=user.id)
        preferred_language = preferences.preferred_language if preferences is not None else None
        email_sent = await send_email(
            to_address=user.email,
            subject=onboarding_welcome_subject(display_name=user.display_name, preferred_language=preferred_language),
            html_body=onboarding_welcome_html(
                display_name=user.display_name, onboard_url=onboard_url, preferred_language=preferred_language
            ),
            text_body=onboarding_welcome_text(
                display_name=user.display_name, onboard_url=onboard_url, preferred_language=preferred_language
            ),
        )

    if user.phone_number:
        await send_signal_message(
            user.phone_number, f"Welkom bij CollaBrains! Start hier: {onboard_url}"
        )

    return email_sent
