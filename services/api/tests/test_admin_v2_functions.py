from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from api.config import settings
from api.ldap_auth import LdapIdentity


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


def _unique_phone() -> str:
    return f"+1{uuid4().int % 10_000_000_000:010d}"


async def _login(client, username: str, *, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _create_bug_report(client, token: str, description: str = "it broke") -> str:
    response = await client.post(
        "/admin/bug-reports", headers={"Authorization": f"Bearer {token}"}, json={"description": description}
    )
    return response.json()["id"]


# --- health/service/{name} + services/{name}/logs -------------------------


async def test_health_service_requires_admin_role(client):
    token = await _login(client, _unique("healthservicemember"))
    response = await client.get("/admin/health/service/postgres", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_health_service_returns_postgres_status(client):
    token = await _login(client, _unique("healthserviceadmin"), is_admin=True)
    response = await client.get("/admin/health/service/postgres", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["name"] == "postgres"


async def test_health_service_unknown_name_returns_404(client):
    token = await _login(client, _unique("healthserviceunknown"), is_admin=True)
    response = await client.get("/admin/health/service/carrier-pigeon", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


async def test_service_logs_database_returns_counts(client):
    token = await _login(client, _unique("servicelogsadmin"), is_admin=True)
    response = await client.get("/admin/services/database/logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert "documents" in body and "users" in body and "bug_reports" in body


async def test_service_logs_unknown_name_returns_404(client):
    token = await _login(client, _unique("servicelogsunknown"), is_admin=True)
    response = await client.get("/admin/services/carrier-pigeon/logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


# --- bug report lifecycle --------------------------------------------------


async def test_update_bug_report_status(client):
    reporter_token = await _login(client, _unique("statusreporter"))
    bug_report_id = await _create_bug_report(client, reporter_token)

    admin_token = await _login(client, _unique("statusadmin"), is_admin=True)
    response = await client.put(
        f"/admin/bug-reports/{bug_report_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "closed"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


async def test_update_status_unknown_report_returns_404(client):
    admin_token = await _login(client, _unique("status404admin"), is_admin=True)
    response = await client.put(
        f"/admin/bug-reports/{uuid4()}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "closed"},
    )
    assert response.status_code == 404


async def test_delete_bug_report(client):
    reporter_token = await _login(client, _unique("deletereporter"))
    bug_report_id = await _create_bug_report(client, reporter_token)

    admin_token = await _login(client, _unique("deleteadmin"), is_admin=True)
    response = await client.delete(
        f"/admin/bug-reports/{bug_report_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 204

    listing = await client.get("/admin/bug-reports", headers={"Authorization": f"Bearer {admin_token}"})
    assert bug_report_id not in [row["id"] for row in listing.json()]


async def test_delete_unknown_bug_report_returns_404(client):
    admin_token = await _login(client, _unique("delete404admin"), is_admin=True)
    response = await client.delete(
        f"/admin/bug-reports/{uuid4()}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


async def test_bulk_delete_bug_reports(client):
    reporter_token = await _login(client, _unique("bulkdeletereporter"))
    id_a = await _create_bug_report(client, reporter_token, "bug a")
    id_b = await _create_bug_report(client, reporter_token, "bug b")
    missing_id = str(uuid4())

    admin_token = await _login(client, _unique("bulkdeleteadmin"), is_admin=True)
    response = await client.request(
        "DELETE",
        "/admin/bug-reports",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"ids": [id_a, id_b, missing_id]},
    )
    assert response.status_code == 200
    assert response.json()["deleted"] == 2


async def test_clarify_generates_questions(client):
    reporter_token = await _login(client, _unique("clarifyreporter"))
    bug_report_id = await _create_bug_report(client, reporter_token, "page is broken somehow")

    admin_token = await _login(client, _unique("clarifyadmin"), is_admin=True)
    fake_response = '{"questions": ["Which page?", "What browser?"]}'
    with patch("api.admin_service.chat_completion", AsyncMock(return_value=fake_response)):
        response = await client.post(
            f"/admin/bug-reports/{bug_report_id}/clarify", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 200
    assert response.json()["questions"] == ["Which page?", "What browser?"]


async def test_clarify_with_no_questions_returns_422(client):
    reporter_token = await _login(client, _unique("clarifyemptyreporter"))
    bug_report_id = await _create_bug_report(client, reporter_token, "already very detailed report")

    admin_token = await _login(client, _unique("clarifyemptyadmin"), is_admin=True)
    with patch("api.admin_service.chat_completion", AsyncMock(return_value='{"questions": []}')):
        response = await client.post(
            f"/admin/bug-reports/{bug_report_id}/clarify", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 422


async def test_codeberg_issue_returns_503_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "codeberg_api_token", "")
    reporter_token = await _login(client, _unique("codebergreporter"))
    bug_report_id = await _create_bug_report(client, reporter_token)

    admin_token = await _login(client, _unique("codebergadmin"), is_admin=True)
    response = await client.post(
        f"/admin/bug-reports/{bug_report_id}/codeberg-issue", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 503


async def test_codeberg_issue_creates_and_is_idempotent(client, monkeypatch):
    # Mocks api.admin_service.httpx.AsyncClient.post and calls the service
    # function directly (not through the HTTP `client` fixture) -- patching
    # httpx.AsyncClient globally would also break the ASGI test client
    # itself, since it's built on httpx.AsyncClient too (see
    # test_admin_service.py::test_get_service_health_reports_down_on_connection_error
    # for the same pattern).
    from api.admin_service import create_codeberg_issue
    from api.db import async_session

    monkeypatch.setattr(settings, "codeberg_api_token", "fake-token")
    monkeypatch.setattr(settings, "codeberg_repo", "collabrains/next")
    reporter_token = await _login(client, _unique("codebergokreporter"))
    bug_report_id = UUID(await _create_bug_report(client, reporter_token))

    fake_issue = {"html_url": "https://codeberg.org/collabrains/next/issues/42", "number": 42}
    mock_response = AsyncMock()
    mock_response.json = lambda: fake_issue
    mock_response.raise_for_status = lambda: None

    async with async_session() as db:
        with patch("api.admin_service.httpx.AsyncClient.post", AsyncMock(return_value=mock_response)) as mock_post:
            report = await create_codeberg_issue(db, bug_report_id=bug_report_id)
        assert report.codeberg_issue_number == 42
        mock_post.assert_called_once()

        # Second call must not hit the network again -- already has a URL.
        with patch("api.admin_service.httpx.AsyncClient.post", AsyncMock(return_value=mock_response)) as mock_post_again:
            report_again = await create_codeberg_issue(db, bug_report_id=bug_report_id)
        assert report_again.codeberg_issue_number == 42
        mock_post_again.assert_not_called()


async def test_analyze_all_starts_and_reports_status(client):
    admin_token = await _login(client, _unique("analyzealladmin"), is_admin=True)
    with patch("api.admin_service.chat_completion", AsyncMock(return_value="Looks minor.")):
        start = await client.post(
            "/admin/bug-reports/analyze-all", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert start.status_code == 200
        assert start.json()["started"] is True

        status_response = await client.get(
            "/admin/bug-reports/analyze-all/status", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert status_response.status_code == 200
    assert "running" in status_response.json()


# --- signal lookup ----------------------------------------------------------


async def test_signal_lookup_requires_admin_role(client):
    token = await _login(client, _unique("signallookupmember"))
    response = await client.get(
        "/admin/signal-lookup", headers={"Authorization": f"Bearer {token}"}, params={"phone": "+15551234567"}
    )
    assert response.status_code == 403


async def test_signal_lookup_finds_user_by_phone(client):
    phone = _unique_phone()
    username = _unique("signallookupuser")
    token = await _login(client, username)
    link = await client.put(
        "/auth/me/phone", headers={"Authorization": f"Bearer {token}"}, json={"phone_number": phone}
    )
    assert link.status_code == 200

    admin_token = await _login(client, _unique("signallookupadmin"), is_admin=True)
    response = await client.get(
        "/admin/signal-lookup",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"phone": phone},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == username


async def test_signal_lookup_unknown_phone_returns_404(client):
    admin_token = await _login(client, _unique("signallookup404admin"), is_admin=True)
    response = await client.get(
        "/admin/signal-lookup", headers={"Authorization": f"Bearer {admin_token}"}, params={"phone": _unique_phone()}
    )
    assert response.status_code == 404


async def test_signal_lookup_internal_rejects_bad_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_secret", "correct-secret")
    response = await client.get(
        "/admin/signal-lookup-internal",
        params={"phone": _unique_phone()},
        headers={"X-Internal-Secret": "wrong-secret"},
    )
    assert response.status_code == 403


async def test_signal_lookup_internal_rejects_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_secret", "")
    response = await client.get(
        "/admin/signal-lookup-internal",
        params={"phone": _unique_phone()},
        headers={"X-Internal-Secret": "anything"},
    )
    assert response.status_code == 403


async def test_signal_lookup_internal_accepts_correct_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_secret", "correct-secret")
    phone = _unique_phone()
    username = _unique("signalinternaluser")
    token = await _login(client, username)
    await client.put("/auth/me/phone", headers={"Authorization": f"Bearer {token}"}, json={"phone_number": phone})

    response = await client.get(
        "/admin/signal-lookup-internal",
        params={"phone": phone},
        headers={"X-Internal-Secret": "correct-secret"},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == username


async def test_signal_bug_from_text_creates_report(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_secret", "correct-secret")
    username = _unique("signalbuguser")
    await _login(client, username)

    response = await client.post(
        "/admin/signal/bug-from-text",
        headers={"X-Internal-Secret": "correct-secret"},
        json={"text": "the app crashed when I uploaded a photo", "owner_uid": username},
    )
    assert response.status_code == 200
    assert "id" in response.json()


async def test_signal_bug_from_text_unknown_owner_returns_404(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_secret", "correct-secret")
    response = await client.post(
        "/admin/signal/bug-from-text",
        headers={"X-Internal-Secret": "correct-secret"},
        json={"text": "hello", "owner_uid": "no-such-user"},
    )
    assert response.status_code == 404


async def test_signal_bug_from_text_rejects_bad_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_secret", "correct-secret")
    response = await client.post(
        "/admin/signal/bug-from-text",
        headers={"X-Internal-Secret": "wrong-secret"},
        json={"text": "hello", "owner_uid": "whoever"},
    )
    assert response.status_code == 403
