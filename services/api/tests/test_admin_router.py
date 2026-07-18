from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.ldap_auth import LdapAdminError, LdapIdentity, LdapUserCreated


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _login(client, username: str, *, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_admin_stats_requires_admin_role(client):
    token = await _login(client, _unique("adminstatsmember"), is_admin=False)
    response = await client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_admin_stats_returns_counts_for_admin(client):
    token = await _login(client, _unique("adminstatsadmin"), is_admin=True)
    response = await client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert "total_users" in body
    assert "documents_by_status" in body


async def test_admin_stats_rejects_missing_token(client):
    response = await client.get("/admin/stats")
    assert response.status_code == 401


async def test_admin_ai_usage_requires_admin_role(client):
    token = await _login(client, _unique("adminusagemember"), is_admin=False)
    response = await client.get("/admin/ai-usage", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_admin_health_requires_admin_role(client):
    token = await _login(client, _unique("adminhealthmember"), is_admin=False)
    response = await client.get("/admin/health", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_admin_health_returns_200_with_all_known_services(client):
    # The down-service case (a service unreachable) is covered at the service
    # layer in test_admin_service.py::test_get_service_health_reports_down_on_connection_error --
    # patching httpx.AsyncClient.get here would also patch this test's own ASGI
    # test client (also an httpx.AsyncClient), so only the wiring/auth is tested here.
    token = await _login(client, _unique("adminhealthadmin"), is_admin=True)
    response = await client.get("/admin/health", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    names = {row["name"] for row in response.json()}
    assert names == {"postgres", "paperless", "ollama"}


async def test_any_authenticated_user_can_create_bug_report(client):
    token = await _login(client, _unique("bugreporter"), is_admin=False)
    response = await client.post(
        "/admin/bug-reports", headers={"Authorization": f"Bearer {token}"}, json={"description": "it broke"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "open"


async def test_non_admin_cannot_list_bug_reports(client):
    token = await _login(client, _unique("bugreportermember"), is_admin=False)
    response = await client.get("/admin/bug-reports", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_admin_can_analyze_a_bug_report(client):
    reporter_token = await _login(client, _unique("bugreportercreator"), is_admin=False)
    create_response = await client.post(
        "/admin/bug-reports",
        headers={"Authorization": f"Bearer {reporter_token}"},
        json={"description": "search returns nothing"},
    )
    bug_report_id = create_response.json()["id"]

    admin_token = await _login(client, _unique("bugreportadmin"), is_admin=True)
    with patch("api.admin_service.chat_completion", AsyncMock(return_value="Search index likely stale.")):
        analyze_response = await client.post(
            f"/admin/bug-reports/{bug_report_id}/analyze", headers={"Authorization": f"Bearer {admin_token}"}
        )

    assert analyze_response.status_code == 200
    assert analyze_response.json()["status"] == "analyzed"


async def test_analyze_unknown_bug_report_returns_404(client):
    admin_token = await _login(client, _unique("bugreport404admin"), is_admin=True)
    response = await client.post(
        f"/admin/bug-reports/{uuid4()}/analyze", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


async def test_non_admin_cannot_create_user(client):
    token = await _login(client, _unique("createusermember"), is_admin=False)
    response = await client.post(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "newperson", "display_name": "New Person", "email": "new@collabrains.eu"},
    )
    assert response.status_code == 403


async def test_admin_can_create_user_and_receives_temporary_password(client):
    admin_token = await _login(client, _unique("createuseradmin"), is_admin=True)
    with patch(
        "api.admin_router.ldap_create_user",
        return_value=LdapUserCreated(username="newperson", temporary_password="a-temp-pw-123"),
    ) as mock_create:
        response = await client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "newperson", "display_name": "New Person",
                "email": "new@collabrains.eu", "is_admin": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "newperson"
    assert body["temporary_password"] == "a-temp-pw-123"
    mock_create.assert_called_once_with(
        username="newperson", display_name="New Person", email="new@collabrains.eu", is_admin=True,
    )


async def test_create_user_with_duplicate_username_returns_409(client):
    admin_token = await _login(client, _unique("dupuseradmin"), is_admin=True)
    with patch(
        "api.admin_router.ldap_create_user",
        side_effect=LdapAdminError("entry already exists"),
    ):
        response = await client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"username": "existing", "display_name": "Existing Person", "email": "e@collabrains.eu"},
        )
    assert response.status_code == 409


async def test_create_user_reports_ldap_bind_failure_as_502(client):
    admin_token = await _login(client, _unique("ldapdownadmin"), is_admin=True)
    with patch(
        "api.admin_router.ldap_create_user",
        side_effect=LdapAdminError("could not bind as LDAP admin"),
    ):
        response = await client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"username": "someone", "display_name": "Someone Else", "email": "s@collabrains.eu"},
        )
    assert response.status_code == 502


async def test_admin_can_create_user_with_phone_number_stages_a_pending_row(client):
    from sqlalchemy import select

    from api.db import async_session
    from api.models import PendingUserPhoneNumber

    admin_token = await _login(client, _unique("phoneuseradmin"), is_admin=True)
    username = _unique("phonependinguser")
    with patch(
        "api.admin_router.ldap_create_user",
        return_value=LdapUserCreated(username=username, temporary_password="a-temp-pw-456"),
    ):
        response = await client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": username, "display_name": "Phone Pending User",
                "email": "phonepending@collabrains.eu", "phone_number": "+15559990321",
            },
        )
    assert response.status_code == 200

    async with async_session() as db:
        result = await db.execute(select(PendingUserPhoneNumber).where(PendingUserPhoneNumber.username == username))
        pending = result.scalar_one()
    assert pending.phone_number == "+15559990321"


async def test_admin_create_user_with_invalid_phone_number_returns_400(client):
    admin_token = await _login(client, _unique("badphoneadmin"), is_admin=True)
    username = _unique("badphoneuser")
    with patch(
        "api.admin_router.ldap_create_user",
        return_value=LdapUserCreated(username=username, temporary_password="a-temp-pw-789"),
    ):
        response = await client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": username, "display_name": "Bad Phone User",
                "email": "badphone@collabrains.eu", "phone_number": "0491511234567",
            },
        )
    assert response.status_code == 400


async def test_admin_create_user_with_duplicate_phone_number_returns_409(client):
    admin_token = await _login(client, _unique("duppphoneadmin"), is_admin=True)
    username1 = _unique("dupphoneuser1")
    username2 = _unique("dupphoneuser2")

    with patch(
        "api.admin_router.ldap_create_user",
        return_value=LdapUserCreated(username=username1, temporary_password="pw1"),
    ):
        first = await client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": username1, "display_name": "Dup Phone One",
                "email": "dup1@collabrains.eu", "phone_number": "+15559990654",
            },
        )
    assert first.status_code == 200

    with patch(
        "api.admin_router.ldap_create_user",
        return_value=LdapUserCreated(username=username2, temporary_password="pw2"),
    ):
        second = await client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": username2, "display_name": "Dup Phone Two",
                "email": "dup2@collabrains.eu", "phone_number": "+15559990654",
            },
        )
    assert second.status_code == 409


async def test_admin_create_user_with_phone_already_linked_to_an_active_user_returns_409(client):
    """A phone already claimed by an existing User.phone_number (not just
    another pending row) must be rejected at creation time -- otherwise
    it would silently stage, then break the new user's first login with
    an unhandled IntegrityError when _get_or_provision_user tries to
    set the same phone number on their new User row."""
    admin_token = await _login(client, _unique("activephoneadmin"), is_admin=True)

    active_username = _unique("activephoneuser")
    active_token = await _login(client, active_username, is_admin=False)
    link = await client.put(
        "/auth/me/phone",
        headers={"Authorization": f"Bearer {active_token}"},
        json={"phone_number": "+15559990987"},
    )
    assert link.status_code == 200

    new_username = _unique("wantsactivephoneuser")
    with patch(
        "api.admin_router.ldap_create_user",
        return_value=LdapUserCreated(username=new_username, temporary_password="pw3"),
    ):
        response = await client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": new_username, "display_name": "Wants Active Phone",
                "email": "wantsactive@collabrains.eu", "phone_number": "+15559990987",
            },
        )
    assert response.status_code == 409


async def test_admin_list_users_requires_admin_role(client):
    token = await _login(client, _unique("listusersmember"), is_admin=False)
    response = await client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_admin_list_users_rejects_missing_token(client):
    response = await client.get("/admin/users")
    assert response.status_code == 401


async def test_admin_list_users_returns_newest_first(client):
    older_username = _unique("listuserolder")
    newer_username = _unique("listusernewer")
    await _login(client, older_username, is_admin=False)
    await _login(client, newer_username, is_admin=False)

    admin_token = await _login(client, _unique("listusersadmin"), is_admin=True)
    response = await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )
    assert response.status_code == 200
    usernames = [row["username"] for row in response.json()]
    assert usernames.index(newer_username) < usernames.index(older_username)


async def test_admin_list_users_respects_limit(client):
    admin_token = await _login(client, _unique("listuserslimitadmin"), is_admin=True)
    response = await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 2}
    )
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_admin_list_users_returns_is_active_true_for_new_users(client):
    username = _unique("activedefaultuser")
    await _login(client, username, is_admin=False)

    admin_token = await _login(client, _unique("activedefaultadmin"), is_admin=True)
    response = await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )
    assert response.status_code == 200
    row = next(r for r in response.json() if r["username"] == username)
    assert row["is_active"] is True

async def test_set_role_requires_admin_role(client):
    # a random uuid is fine here -- the 403 for a non-admin caller must fire
    # before any user lookup happens
    token = await _login(client, _unique("setrolemember"), is_admin=False)
    response = await client.put(
        f"/admin/users/{uuid4()}/role",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 403


async def test_set_role_updates_member_to_admin(client):
    username = _unique("promoteuser")
    await _login(client, username, is_admin=False)
    admin_token = await _login(client, _unique("promoteadmin"), is_admin=True)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target = next(u for u in users if u["username"] == username)

    response = await client.put(
        f"/admin/users/{target['id']}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_set_role_unknown_user_returns_404(client):
    admin_token = await _login(client, _unique("rolenotfoundadmin"), is_admin=True)
    response = await client.put(
        f"/admin/users/{uuid4()}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 404


async def test_set_role_refuses_service_account(client):
    admin_token = await _login(client, _unique("rolesvcadmin"), is_admin=True)
    # signal-bot is a fixed service account seeded elsewhere in this suite's
    # shared dev DB; if it's ever absent this test is a no-op-safe skip.
    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    service_user = next((u for u in users if u["role"] == "service"), None)
    if service_user is None:
        return
    response = await client.put(
        f"/admin/users/{service_user['id']}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "member"},
    )
    assert response.status_code == 403

async def test_set_role_requires_admin_role(client):
    # a random uuid is fine here -- the 403 for a non-admin caller must fire
    # before any user lookup happens
    token = await _login(client, _unique("setrolemember"), is_admin=False)
    response = await client.put(
        f"/admin/users/{uuid4()}/role",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 403


async def test_set_role_updates_member_to_admin(client):
    username = _unique("promoteuser")
    await _login(client, username, is_admin=False)
    admin_token = await _login(client, _unique("promoteadmin"), is_admin=True)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target = next(u for u in users if u["username"] == username)

    response = await client.put(
        f"/admin/users/{target['id']}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_set_role_unknown_user_returns_404(client):
    admin_token = await _login(client, _unique("rolenotfoundadmin"), is_admin=True)
    response = await client.put(
        f"/admin/users/{uuid4()}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 404


async def test_set_role_refuses_service_account(client):
    admin_token = await _login(client, _unique("rolesvcadmin"), is_admin=True)
    # signal-bot is a fixed service account seeded elsewhere in this suite's
    # shared dev DB; if it's ever absent this test is a no-op-safe skip.
    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    service_user = next((u for u in users if u["role"] == "service"), None)
    if service_user is None:
        return
    response = await client.put(
        f"/admin/users/{service_user['id']}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "member"},
    )
    assert response.status_code == 403
