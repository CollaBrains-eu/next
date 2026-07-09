from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.ldap_auth import LdapIdentity


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
