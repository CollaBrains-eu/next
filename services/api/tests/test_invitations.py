from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy import select

from api.config import settings
from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Invitation, Organization, User


def _unique(base: str) -> str:
    return f"{base}{uuid4().hex[:10]}"


async def _login(client, username: str, *, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_by_username(username: str) -> User:
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalars().one()


async def _invitation_by_email(email: str) -> Invitation:
    async with async_session() as db:
        result = await db.execute(select(Invitation).where(Invitation.email == email))
        return result.scalars().one()


async def _move_to_new_org(username: str) -> str:
    """Puts this user in a brand-new Organization, isolated from
    DEFAULT_ORGANIZATION_ID -- every plain _login() defaults into that
    same shared org, which would make an "already a member" check against
    some other test's existing user collide here."""
    async with async_session() as db:
        organization = Organization(name=f"org-for-{username}")
        db.add(organization)
        await db.flush()
        user = (await db.execute(select(User).where(User.username == username))).scalar_one()
        user.organization_id = organization.id
        await db.commit()
        return str(organization.id)


# --- POST/GET/DELETE /organizations/me/invitations (sender side) --------


async def test_non_admin_non_owner_cannot_send_invitations(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    token = await _login(client, _unique("invitesendermember"))
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/organizations/me/invitations", headers=headers, json={"email": "invitee@example.com"}
    )
    assert response.status_code == 403


async def test_platform_admin_can_send_invitation_and_it_gets_emailed(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_username", "user")
    monkeypatch.setattr(settings, "smtp_password", "pass")

    token = await _login(client, _unique("inviteadmin"), is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}
    invitee_email = f"{_unique('invitee')}@example.com"

    with patch("api.invitation_service.send_email", AsyncMock(return_value=True)) as mock_send:
        response = await client.post(
            "/organizations/me/invitations", headers=headers, json={"email": invitee_email}
        )
    assert response.status_code == 201
    assert response.json()["email"] == invitee_email
    mock_send.assert_called_once()

    invitation = await _invitation_by_email(invitee_email)
    assert invitation.accepted_at is None
    assert invitation.revoked_at is None


async def test_org_owner_without_platform_admin_can_send_invitation(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    username = _unique("orginviteowner")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}

    org_id = (await client.get("/organizations/me", headers=headers)).json()["id"]
    user = await _user_by_username(username)
    async with async_session() as db:
        organization = await db.get(Organization, org_id)
        organization.owner_user_id = user.id
        await db.commit()

    try:
        response = await client.post(
            "/organizations/me/invitations", headers=headers, json={"email": f"{_unique('owned')}@example.com"}
        )
        assert response.status_code == 201
    finally:
        async with async_session() as db:
            organization = await db.get(Organization, org_id)
            organization.owner_user_id = None
            await db.commit()


async def test_invite_rejects_invalid_email(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    token = await _login(client, _unique("inviteadminbademail"), is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/organizations/me/invitations", headers=headers, json={"email": "not-an-email"})
    assert response.status_code == 400


async def test_invite_rejects_already_a_member(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    admin_token = await _login(client, _unique("inviteadminexisting"), is_admin=True)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    member_username = _unique("invitealreadymember")
    await _login(client, member_username)
    member = await _user_by_username(member_username)

    response = await client.post(
        "/organizations/me/invitations", headers=admin_headers, json={"email": member.email}
    )
    assert response.status_code == 409


async def test_inviting_same_email_again_resends_instead_of_duplicating(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    token = await _login(client, _unique("inviteresendadmin"), is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}
    invitee_email = f"{_unique('resendinvitee')}@example.com"

    first = await client.post("/organizations/me/invitations", headers=headers, json={"email": invitee_email})
    first_id = first.json()["id"]

    second = await client.post("/organizations/me/invitations", headers=headers, json={"email": invitee_email})
    assert second.status_code == 201
    assert second.json()["id"] == first_id  # same row, refreshed, not a duplicate

    async with async_session() as db:
        result = await db.execute(select(Invitation).where(Invitation.email == invitee_email))
        assert len(result.scalars().all()) == 1


async def test_list_invitations_only_shows_pending(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    token = await _login(client, _unique("invitelistadmin"), is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}
    invitee_email = f"{_unique('listedinvitee')}@example.com"

    create_response = await client.post(
        "/organizations/me/invitations", headers=headers, json={"email": invitee_email}
    )
    invitation_id = create_response.json()["id"]

    listing = await client.get("/organizations/me/invitations", headers=headers)
    assert any(row["id"] == invitation_id for row in listing.json())

    revoke_response = await client.delete(f"/organizations/me/invitations/{invitation_id}", headers=headers)
    assert revoke_response.status_code == 204

    listing_after = await client.get("/organizations/me/invitations", headers=headers)
    assert all(row["id"] != invitation_id for row in listing_after.json())


async def test_revoke_unknown_invitation_returns_404(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    token = await _login(client, _unique("inviterevoke404admin"), is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/organizations/me/invitations/{uuid4()}", headers=headers)
    assert response.status_code == 404


# --- GET /invitations/{token}, POST /invitations/{token}/accept (recipient side) --


async def test_check_invitation_reports_valid_org_name_and_account_exists(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    admin_username = _unique("invitecheckadmin")
    admin_token = await _login(client, admin_username, is_admin=True)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    await _move_to_new_org(admin_username)

    existing_username = _unique("invitecheckexisting")
    await _login(client, existing_username)
    existing_user = await _user_by_username(existing_username)

    create_response = await client.post(
        "/organizations/me/invitations", headers=admin_headers, json={"email": existing_user.email}
    )
    invitation = await _invitation_by_email(existing_user.email)
    assert create_response.status_code == 201

    check = await client.get(f"/invitations/{invitation.token}")
    assert check.status_code == 200
    body = check.json()
    assert body["valid"] is True
    assert body["email"] == existing_user.email
    assert body["account_exists"] is True


async def test_check_invitation_unknown_token_is_invalid(client):
    response = await client.get("/invitations/does-not-exist")
    assert response.status_code == 200
    assert response.json()["valid"] is False


async def test_accept_invitation_switches_existing_user_into_the_org(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    admin_username = _unique("inviteacceptadmin")
    admin_token = await _login(client, admin_username, is_admin=True)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_org_id = await _move_to_new_org(admin_username)

    invitee_username = _unique("inviteacceptexisting")
    invitee_token = await _login(client, invitee_username)
    invitee_headers = {"Authorization": f"Bearer {invitee_token}"}
    invitee_user = await _user_by_username(invitee_username)

    await client.post("/organizations/me/invitations", headers=admin_headers, json={"email": invitee_user.email})
    invitation = await _invitation_by_email(invitee_user.email)

    accept_response = await client.post(f"/invitations/{invitation.token}/accept", headers=invitee_headers)
    assert accept_response.status_code == 200
    assert "access_token" in accept_response.json()

    updated_user = await _user_by_username(invitee_username)
    assert str(updated_user.organization_id) == admin_org_id

    async with async_session() as db:
        refreshed = await db.get(Invitation, invitation.id)
        assert refreshed.accepted_at is not None


async def test_accept_invitation_twice_fails_the_second_time(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    admin_username = _unique("inviteaccepttwiceadmin")
    admin_token = await _login(client, admin_username, is_admin=True)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    await _move_to_new_org(admin_username)

    invitee_username = _unique("inviteaccepttwiceuser")
    invitee_token = await _login(client, invitee_username)
    invitee_headers = {"Authorization": f"Bearer {invitee_token}"}
    invitee_user = await _user_by_username(invitee_username)

    await client.post("/organizations/me/invitations", headers=admin_headers, json={"email": invitee_user.email})
    invitation = await _invitation_by_email(invitee_user.email)

    first = await client.post(f"/invitations/{invitation.token}/accept", headers=invitee_headers)
    assert first.status_code == 200

    second = await client.post(f"/invitations/{invitation.token}/accept", headers=invitee_headers)
    assert second.status_code == 400


async def test_accept_invitation_rejects_missing_token(client):
    response = await client.post(f"/invitations/{uuid4()}/accept")
    assert response.status_code == 401


# --- Invitation-carrying self-service registration ------------------------


def _register_body(username: str, **overrides) -> dict:
    body = {
        "username": username,
        "display_name": "Invited Signup",
        "email": f"{username}@example.com",
        "password": "correct-horse-battery",
    }
    body.update(overrides)
    return body


async def test_register_with_invitation_token_joins_the_inviting_org_not_a_new_one(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    admin_token = await _login(client, _unique("invitedregadmin"), is_admin=True)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_org_id = (await client.get("/organizations/me", headers=admin_headers)).json()["id"]

    invitee_username = _unique("invitedreguser")
    invitee_email = f"{invitee_username}@example.com"
    await client.post("/organizations/me/invitations", headers=admin_headers, json={"email": invitee_email})
    invitation = await _invitation_by_email(invitee_email)

    register_response = await client.post(
        "/auth/register",
        json=_register_body(invitee_username, email=invitee_email, invitation_token=invitation.token),
    )
    assert register_response.status_code == 201

    async with async_session() as db:
        from api.models import PendingRegistration

        pending = (
            await db.execute(select(PendingRegistration).where(PendingRegistration.username == invitee_username))
        ).scalars().one()

    with patch("api.registration_service.ldap_register_user", return_value=None):
        verify_response = await client.post("/auth/verify-email", json={"token": pending.token})
    assert verify_response.status_code == 200

    new_user = await _user_by_username(invitee_username)
    assert str(new_user.organization_id) == admin_org_id

    async with async_session() as db:
        organization = await db.get(Organization, admin_org_id)
        # Joining an existing org must never make the invitee its owner.
        assert organization.owner_user_id != new_user.id

        refreshed_invitation = await db.get(Invitation, invitation.id)
        assert refreshed_invitation.accepted_at is not None


async def test_register_with_invitation_token_rejects_mismatched_email(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    admin_token = await _login(client, _unique("invitedregmismatchadmin"), is_admin=True)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    invitee_email = f"{_unique('mismatchinvitee')}@example.com"
    await client.post("/organizations/me/invitations", headers=admin_headers, json={"email": invitee_email})
    invitation = await _invitation_by_email(invitee_email)

    response = await client.post(
        "/auth/register",
        json=_register_body(
            _unique("mismatchreguser"), email="someone-else@example.com", invitation_token=invitation.token
        ),
    )
    assert response.status_code == 400


async def test_register_rejects_unknown_invitation_token(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    response = await client.post(
        "/auth/register", json=_register_body(_unique("badinvitereguser"), invitation_token="does-not-exist")
    )
    assert response.status_code == 400
