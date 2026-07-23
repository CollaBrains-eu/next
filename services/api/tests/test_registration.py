from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy import select

from api.config import settings
from api.db import async_session
from api.ldap_auth import LdapAdminError
from api.models import Organization, PendingRegistration, User
from api.registration_service import check_registration_rate_limit


def _unique(base: str) -> str:
    return f"{base}{uuid4().hex[:10]}"


def _register_body(username: str, **overrides) -> dict:
    body = {
        "username": username,
        "display_name": "New Signup",
        "email": f"{username}@example.com",
        "password": "correct-horse-battery",
    }
    body.update(overrides)
    return body


async def _pending_registration_for(username: str) -> PendingRegistration:
    async with async_session() as db:
        result = await db.execute(select(PendingRegistration).where(PendingRegistration.username == username))
        return result.scalars().one()


# --- POST /auth/register --------------------------------------------------


async def test_register_creates_pending_registration_and_sends_email(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_username", "user")
    monkeypatch.setattr(settings, "smtp_password", "pass")

    username = _unique("signupuser")
    with patch("api.registration_service.send_email", AsyncMock(return_value=True)) as mock_send:
        response = await client.post("/auth/register", json=_register_body(username))

    assert response.status_code == 201
    assert response.json()["email_sent"] is True
    mock_send.assert_called_once()

    record = await _pending_registration_for(username)
    assert record.email == f"{username}@example.com"
    assert record.consumed_at is None
    # The stored hash must not be the plaintext password.
    assert record.password_hash != "correct-horse-battery"


async def test_register_reports_email_not_sent_when_smtp_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")

    username = _unique("signupnosmtp")
    response = await client.post("/auth/register", json=_register_body(username))

    assert response.status_code == 201
    assert response.json()["email_sent"] is False
    # The pending registration still exists -- an admin/support flow could
    # still retrieve the token even though no email went out automatically.
    record = await _pending_registration_for(username)
    assert record is not None


async def test_register_defaults_organization_name_from_display_name(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    username = _unique("signuporgdefault")

    await client.post("/auth/register", json=_register_body(username, display_name="Ada Lovelace"))

    record = await _pending_registration_for(username)
    assert record.organization_name == "Ada Lovelace's organization"


async def test_register_honors_explicit_organization_name(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    username = _unique("signuporgcustom")

    await client.post("/auth/register", json=_register_body(username, organization_name="Acme Legal"))

    record = await _pending_registration_for(username)
    assert record.organization_name == "Acme Legal"


async def test_register_rejects_invalid_username(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    response = await client.post("/auth/register", json=_register_body("Not Valid!"))
    assert response.status_code == 400


async def test_register_rejects_invalid_email(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    response = await client.post(
        "/auth/register", json=_register_body(_unique("signupbademail"), email="not-an-email")
    )
    assert response.status_code == 400


async def test_register_rejects_short_password(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    response = await client.post(
        "/auth/register", json=_register_body(_unique("signupshortpw"), password="short")
    )
    assert response.status_code == 400


async def test_register_rejects_username_already_confirmed(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    username = _unique("signuptaken")
    async with async_session() as db:
        db.add(User(username=username, display_name=username, role="member"))
        await db.commit()

    response = await client.post("/auth/register", json=_register_body(username))
    assert response.status_code == 409


async def test_register_rejects_email_already_confirmed(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    email = f"{_unique('signupemailtaken')}@example.com"
    async with async_session() as db:
        db.add(User(username=_unique("signupemailowner"), display_name="Owner", email=email, role="member"))
        await db.commit()

    response = await client.post(
        "/auth/register", json=_register_body(_unique("signupnewusername"), email=email)
    )
    assert response.status_code == 409


async def test_register_again_with_same_username_resends_instead_of_conflicting(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    username = _unique("signupresend")

    first = await client.post("/auth/register", json=_register_body(username))
    assert first.status_code == 201
    first_token = (await _pending_registration_for(username)).token

    second = await client.post("/auth/register", json=_register_body(username, display_name="Updated Name"))
    assert second.status_code == 201

    record = await _pending_registration_for(username)
    assert record.display_name == "Updated Name"
    assert record.token != first_token  # old link is no longer valid


async def test_register_rate_limit_blocks_after_configured_threshold():
    email = f"{_unique('ratelimit')}@example.com"
    blocked_at = None
    for i in range(settings.registration_rate_limit_per_hour + 3):
        allowed = await check_registration_rate_limit(email)
        if not allowed:
            blocked_at = i + 1
            break
    assert blocked_at == settings.registration_rate_limit_per_hour + 1


# --- POST /auth/verify-email ----------------------------------------------


async def test_verify_email_completes_registration_and_logs_in(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    username = _unique("verifyuser")

    await client.post("/auth/register", json=_register_body(username, organization_name="Verify Co"))
    record = await _pending_registration_for(username)

    with patch("api.registration_service.ldap_register_user", return_value=None) as mock_ldap:
        response = await client.post("/auth/verify-email", json={"token": record.token})

    assert response.status_code == 200
    assert "access_token" in response.json()
    mock_ldap.assert_called_once()
    call_kwargs = mock_ldap.call_args.kwargs
    assert call_kwargs["username"] == username
    assert call_kwargs["password_hash"] == record.password_hash

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == username))).scalar_one()
        # Deliberately still "member" -- role is platform-wide (shared with
        # the LDAP-wide Admin Dashboard), so granting "admin" here would
        # hand every self-service signup platform admin. owner_user_id is
        # the narrow permission that actually lets them manage their org.
        assert user.role == "member"
        org = await db.get(Organization, user.organization_id)
        assert org.name == "Verify Co"
        assert org.owner_user_id == user.id

    refreshed = await _pending_registration_for(username)
    assert refreshed.consumed_at is not None


async def test_verify_email_token_cannot_be_reused(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    username = _unique("verifyreuse")
    await client.post("/auth/register", json=_register_body(username))
    record = await _pending_registration_for(username)

    with patch("api.registration_service.ldap_register_user", return_value=None):
        first = await client.post("/auth/verify-email", json={"token": record.token})
    assert first.status_code == 200

    second = await client.post("/auth/verify-email", json={"token": record.token})
    assert second.status_code == 400


async def test_verify_email_rejects_unknown_token(client):
    response = await client.post("/auth/verify-email", json={"token": "does-not-exist"})
    assert response.status_code == 400


async def test_verify_email_tolerates_ldap_entry_already_existing(client, monkeypatch):
    """Covers a crash between the LDAP write and the Postgres commit on a
    prior attempt: the directory entry already exists, but this token
    hasn't been consumed yet -- should still succeed rather than stranding
    the user."""
    monkeypatch.setattr(settings, "smtp_host", "")
    username = _unique("verifyalreadyldap")
    await client.post("/auth/register", json=_register_body(username))
    record = await _pending_registration_for(username)

    with patch(
        "api.registration_service.ldap_register_user",
        side_effect=LdapAdminError("user already exists"),
    ):
        response = await client.post("/auth/verify-email", json={"token": record.token})

    assert response.status_code == 200
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    assert user is not None
