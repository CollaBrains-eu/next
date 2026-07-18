from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from sqlalchemy import select

from api.config import settings
from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import OnboardingToken, User
from api.onboarding_service import consume_onboarding_token, create_onboarding_token, get_valid_onboarding_token


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _login(client, username: str, *, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_id_for(username: str) -> str:
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == username))).scalar_one()
        return str(user.id)


# --- service layer -----------------------------------------------------


async def test_create_onboarding_token_is_valid_immediately():
    username = _unique("onboardtokenuser")
    async with async_session() as db:
        db.add(User(username=username, display_name=username, role="member"))
        await db.commit()
        user = (await db.execute(select(User).where(User.username == username))).scalar_one()

        token = await create_onboarding_token(db, user_id=user.id)
        valid = await get_valid_onboarding_token(db, token=token.token)
    assert valid is not None
    assert valid.user_id == user.id


async def test_expired_token_is_not_valid():
    username = _unique("onboardexpireduser")
    unique_token = f"expired-{uuid4().hex}"
    async with async_session() as db:
        db.add(User(username=username, display_name=username, role="member"))
        await db.commit()
        user = (await db.execute(select(User).where(User.username == username))).scalar_one()

        db.add(
            OnboardingToken(
                token=unique_token, user_id=user.id, expires_at=datetime.now(timezone.utc) - timedelta(days=1)
            )
        )
        await db.commit()

        result = await get_valid_onboarding_token(db, token=unique_token)
    assert result is None


async def test_consuming_a_token_marks_it_used_and_it_cannot_be_reused():
    username = _unique("onboardconsumeuser")
    async with async_session() as db:
        db.add(User(username=username, display_name=username, role="member"))
        await db.commit()
        user = (await db.execute(select(User).where(User.username == username))).scalar_one()

        token = await create_onboarding_token(db, user_id=user.id)
        consumed = await consume_onboarding_token(db, token=token.token)
        assert consumed is not None
        assert consumed.used_at is not None

        second_attempt = await consume_onboarding_token(db, token=token.token)
    assert second_attempt is None


async def test_unknown_token_is_not_valid():
    async with async_session() as db:
        result = await get_valid_onboarding_token(db, token="does-not-exist")
    assert result is None


# --- admin router --------------------------------------------------------


async def test_resend_welcome_requires_admin_role(client):
    token = await _login(client, _unique("resendwelcomemember"))
    response = await client.post(
        f"/admin/users/{uuid4()}/resend-welcome", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_resend_welcome_unknown_user_returns_404(client):
    admin_token = await _login(client, _unique("resendwelcome404admin"), is_admin=True)
    response = await client.post(
        f"/admin/users/{uuid4()}/resend-welcome", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


async def test_resend_welcome_sends_email_when_smtp_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_username", "user")
    monkeypatch.setattr(settings, "smtp_password", "pass")

    target_username = _unique("resendwelcometarget")
    await _login(client, target_username)
    target_id = await _user_id_for(target_username)

    admin_token = await _login(client, _unique("resendwelcomeadmin"), is_admin=True)
    with patch("api.onboarding_service.send_email", AsyncMock(return_value=True)) as mock_send:
        response = await client.post(
            f"/admin/users/{target_id}/resend-welcome", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 200
    assert response.json()["email_sent"] is True
    mock_send.assert_called_once()

    async with async_session() as db:
        result = await db.execute(select(OnboardingToken).where(OnboardingToken.user_id == UUID(target_id)))
        tokens = result.scalars().all()
    assert len(tokens) == 1


async def test_resend_welcome_email_link_uses_configured_app_base_url(client, monkeypatch):
    """Regression test for a real incident: APP_BASE_URL was never set in
    .env, so onboarding links silently defaulted to https://collabrains.eu
    -- a domain that doesn't resolve -- meaning every welcome email/Signal
    link ever sent was dead. This asserts the link is built from
    settings.app_base_url, not hardcoded."""
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_username", "user")
    monkeypatch.setattr(settings, "smtp_password", "pass")
    monkeypatch.setattr(settings, "app_base_url", "https://example.test")

    target_username = _unique("resendwelcomeurltarget")
    await _login(client, target_username)
    target_id = await _user_id_for(target_username)

    admin_token = await _login(client, _unique("resendwelcomeurladmin"), is_admin=True)
    with patch("api.onboarding_service.send_email", AsyncMock(return_value=True)) as mock_send:
        response = await client.post(
            f"/admin/users/{target_id}/resend-welcome", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 200

    async with async_session() as db:
        result = await db.execute(select(OnboardingToken).where(OnboardingToken.user_id == UUID(target_id)))
        token = result.scalars().one()

    call_kwargs = mock_send.call_args.kwargs
    expected_url = f"https://example.test/onboard?token={token.token}"
    assert expected_url in call_kwargs["text_body"]
    assert expected_url in call_kwargs["html_body"]


async def test_resend_welcome_reports_email_not_sent_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")

    target_username = _unique("resendwelcomeunconfigured")
    await _login(client, target_username)
    target_id = await _user_id_for(target_username)

    admin_token = await _login(client, _unique("resendwelcomeunconfiguredadmin"), is_admin=True)
    response = await client.post(
        f"/admin/users/{target_id}/resend-welcome", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["email_sent"] is False


# --- public onboarding-token check endpoint ------------------------------


async def test_check_onboarding_token_returns_valid_and_user_info(client):
    username = _unique("checktokenuser")
    await _login(client, username)
    user_id = await _user_id_for(username)

    async with async_session() as db:
        token = await create_onboarding_token(db, user_id=UUID(user_id))

    response = await client.get(f"/onboarding/{token.token}")
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["user_id"] == user_id
    assert body["display_name"] == username


async def test_check_onboarding_token_unknown_returns_invalid(client):
    response = await client.get("/onboarding/not-a-real-token")
    assert response.status_code == 200
    assert response.json()["valid"] is False
