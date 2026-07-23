from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy import select

from api.config import settings
from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Organization, Subscription, User


def _unique(base: str) -> str:
    return f"{base}{uuid4().hex[:10]}"


async def _login(client, username: str, *, is_admin: bool = False) -> str:
    identity = LdapIdentity(
        username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=is_admin
    )
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _create_org_and_make_owner(username: str) -> str:
    """Isolated from DEFAULT_ORGANIZATION_ID, which every plain _login()
    shares -- billing state (Subscription is one-per-org) would otherwise
    leak between unrelated tests and across repeated local runs."""
    async with async_session() as db:
        organization = Organization(name=f"org-for-{username}")
        db.add(organization)
        await db.flush()
        user = (await db.execute(select(User).where(User.username == username))).scalar_one()
        user.organization_id = organization.id
        organization.owner_user_id = user.id
        await db.commit()
        return str(organization.id)


def _configure_stripe(monkeypatch, *, starter_price="price_starter_test", pro_price="price_pro_test"):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_price_id_starter", starter_price)
    monkeypatch.setattr(settings, "stripe_price_id_pro", pro_price)


# --- POST /billing/checkout-session ---------------------------------------


async def test_checkout_requires_org_admin(client, monkeypatch):
    _configure_stripe(monkeypatch)
    token = await _login(client, _unique("billingmember"))
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/billing/checkout-session", headers=headers, json={"plan": "pro"})
    assert response.status_code == 403


async def test_checkout_returns_503_when_stripe_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    username = _unique("billingunconfigured")
    token = await _login(client, username, is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/billing/checkout-session", headers=headers, json={"plan": "pro"})
    assert response.status_code == 503


async def test_checkout_rejects_unknown_plan(client, monkeypatch):
    _configure_stripe(monkeypatch)
    token = await _login(client, _unique("billingbadplan"), is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/billing/checkout-session", headers=headers, json={"plan": "not-a-real-plan"})
    assert response.status_code == 400


async def test_checkout_creates_stripe_customer_and_session(client, monkeypatch):
    _configure_stripe(monkeypatch)
    username = _unique("billingcheckout")
    token = await _login(client, username, is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}
    org_id = await _create_org_and_make_owner(username)

    fake_customer_id = _unique("cus_")
    fake_customer = SimpleNamespace(id=fake_customer_id)
    fake_session = SimpleNamespace(url="https://checkout.stripe.com/fake-session")

    with (
        patch("api.billing_service.stripe.Customer.create", return_value=fake_customer) as mock_customer,
        patch("api.billing_service.stripe.checkout.Session.create", return_value=fake_session) as mock_session,
    ):
        response = await client.post("/billing/checkout-session", headers=headers, json={"plan": "pro"})

    assert response.status_code == 200
    assert response.json()["url"] == "https://checkout.stripe.com/fake-session"
    mock_customer.assert_called_once()
    mock_session.assert_called_once()
    call_kwargs = mock_session.call_args.kwargs
    assert call_kwargs["customer"] == fake_customer_id
    assert call_kwargs["client_reference_id"] == org_id
    assert call_kwargs["line_items"] == [{"price": "price_pro_test", "quantity": 1}]

    async with async_session() as db:
        result = await db.execute(select(Subscription).where(Subscription.organization_id == org_id))
        subscription = result.scalar_one()
        assert subscription.stripe_customer_id == fake_customer_id


async def test_checkout_reuses_existing_stripe_customer(client, monkeypatch):
    _configure_stripe(monkeypatch)
    username = _unique("billingreuse")
    token = await _login(client, username, is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}
    await _create_org_and_make_owner(username)

    fake_customer = SimpleNamespace(id=_unique("cus_"))
    fake_session = SimpleNamespace(url="https://checkout.stripe.com/first")

    with (
        patch("api.billing_service.stripe.Customer.create", return_value=fake_customer),
        patch("api.billing_service.stripe.checkout.Session.create", return_value=fake_session),
    ):
        await client.post("/billing/checkout-session", headers=headers, json={"plan": "starter"})

    with (
        patch("api.billing_service.stripe.Customer.create") as mock_customer_second,
        patch(
            "api.billing_service.stripe.checkout.Session.create",
            return_value=SimpleNamespace(url="https://checkout.stripe.com/second"),
        ),
    ):
        second_response = await client.post("/billing/checkout-session", headers=headers, json={"plan": "pro"})

    assert second_response.status_code == 200
    mock_customer_second.assert_not_called()


# --- POST /billing/portal-session ------------------------------------------


async def test_portal_session_requires_org_admin(client, monkeypatch):
    _configure_stripe(monkeypatch)
    token = await _login(client, _unique("billingportalmember"))
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/billing/portal-session", headers=headers)
    assert response.status_code == 403


async def test_portal_session_creates_session(client, monkeypatch):
    _configure_stripe(monkeypatch)
    username = _unique("billingportaladmin")
    token = await _login(client, username, is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}
    await _create_org_and_make_owner(username)

    fake_customer_id = _unique("cus_")
    fake_customer = SimpleNamespace(id=fake_customer_id)
    fake_portal_session = SimpleNamespace(url="https://billing.stripe.com/fake-portal")

    with (
        patch("api.billing_service.stripe.Customer.create", return_value=fake_customer),
        patch("api.billing_service.stripe.billing_portal.Session.create", return_value=fake_portal_session) as mock_portal,
    ):
        response = await client.post("/billing/portal-session", headers=headers)

    assert response.status_code == 200
    assert response.json()["url"] == "https://billing.stripe.com/fake-portal"
    mock_portal.assert_called_once_with(customer=fake_customer_id, return_url=f"{settings.app_base_url}/settings")


# --- GET /billing/subscription ---------------------------------------------


async def test_get_subscription_returns_defaults_for_a_fresh_org(client, monkeypatch):
    username = _unique("billinggetdefault")
    token = await _login(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    await _create_org_and_make_owner(username)

    response = await client.get("/billing/subscription", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["plan"] is None
    assert body["status"] is None
    assert body["cancel_at_period_end"] is False


async def test_get_subscription_readable_by_a_plain_member(client, monkeypatch):
    owner_username = _unique("billinggetowner")
    await _login(client, owner_username)
    org_id = await _create_org_and_make_owner(owner_username)

    member_username = _unique("billinggetplainmember")
    member_token = await _login(client, member_username)
    async with async_session() as db:
        member = (await db.execute(select(User).where(User.username == member_username))).scalar_one()
        member.organization_id = org_id
        await db.commit()

    response = await client.get("/billing/subscription", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200


# --- POST /billing/webhook --------------------------------------------------


def _stripe_event(event_type: str, data_object: dict) -> dict:
    return {"id": f"evt_{uuid4().hex[:10]}", "type": event_type, "data": {"object": data_object}}


async def test_webhook_returns_503_when_not_configured(client):
    response = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "whatever"}
    )
    assert response.status_code == 503


async def test_webhook_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")

    response = await client.post(
        "/billing/webhook", content=b'{"type": "checkout.session.completed"}', headers={"stripe-signature": "bogus"}
    )
    assert response.status_code == 400


async def test_webhook_checkout_completed_links_customer_and_subscription(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")
    org_id = str(uuid4())
    async with async_session() as db:
        db.add(Organization(id=org_id, name="Webhook Org"))
        await db.commit()

    customer_id = _unique("cus_")
    subscription_id = _unique("sub_")
    event = _stripe_event(
        "checkout.session.completed",
        {"customer": customer_id, "subscription": subscription_id, "client_reference_id": org_id},
    )

    with patch("api.billing_router.construct_webhook_event", return_value=event):
        response = await client.post(
            "/billing/webhook", content=b"{}", headers={"stripe-signature": "whatever"}
        )
    assert response.status_code == 204

    async with async_session() as db:
        result = await db.execute(select(Subscription).where(Subscription.organization_id == org_id))
        subscription = result.scalar_one()
        assert subscription.stripe_customer_id == customer_id
        assert subscription.stripe_subscription_id == subscription_id


async def test_webhook_subscription_updated_sets_plan_status_and_period(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")
    monkeypatch.setattr(settings, "stripe_price_id_pro", "price_pro_webhook_test")

    org_id = str(uuid4())
    customer_id = _unique("cus_")
    async with async_session() as db:
        db.add(Organization(id=org_id, name="Webhook Sub Org"))
        db.add(Subscription(organization_id=org_id, stripe_customer_id=customer_id))
        await db.commit()

    period_end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
    event = _stripe_event(
        "customer.subscription.updated",
        {
            "id": _unique("sub_"),
            "customer": customer_id,
            "status": "active",
            "cancel_at_period_end": False,
            "current_period_end": period_end,
            "items": {"data": [{"price": {"id": "price_pro_webhook_test"}}]},
        },
    )

    with patch("api.billing_router.construct_webhook_event", return_value=event):
        response = await client.post(
            "/billing/webhook", content=b"{}", headers={"stripe-signature": "whatever"}
        )
    assert response.status_code == 204

    async with async_session() as db:
        result = await db.execute(select(Subscription).where(Subscription.organization_id == org_id))
        subscription = result.scalar_one()
        assert subscription.plan == "pro"
        assert subscription.status == "active"
        assert subscription.current_period_end is not None


async def test_webhook_subscription_deleted_marks_canceled(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")

    org_id = str(uuid4())
    customer_id = _unique("cus_")
    async with async_session() as db:
        db.add(Organization(id=org_id, name="Webhook Delete Org"))
        db.add(Subscription(organization_id=org_id, stripe_customer_id=customer_id, status="active"))
        await db.commit()

    event = _stripe_event("customer.subscription.deleted", {"id": _unique("sub_"), "customer": customer_id})

    with patch("api.billing_router.construct_webhook_event", return_value=event):
        response = await client.post(
            "/billing/webhook", content=b"{}", headers={"stripe-signature": "whatever"}
        )
    assert response.status_code == 204

    async with async_session() as db:
        result = await db.execute(select(Subscription).where(Subscription.organization_id == org_id))
        assert result.scalar_one().status == "canceled"


async def test_webhook_payment_failed_emails_org_owner(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")

    owner_username = _unique("billingpayfailowner")
    await _login(client, owner_username)
    customer_id = _unique("cus_")
    async with async_session() as db:
        owner_user = (await db.execute(select(User).where(User.username == owner_username))).scalar_one()
        organization = Organization(name="Payment Failed Org", owner_user_id=owner_user.id)
        db.add(organization)
        await db.flush()
        db.add(Subscription(organization_id=organization.id, stripe_customer_id=customer_id, status="active"))
        await db.commit()

    event = _stripe_event("invoice.payment_failed", {"customer": customer_id})

    with (
        patch("api.billing_router.construct_webhook_event", return_value=event),
        patch("api.billing_service.send_email", AsyncMock(return_value=True)) as mock_send,
    ):
        response = await client.post(
            "/billing/webhook", content=b"{}", headers={"stripe-signature": "whatever"}
        )
    assert response.status_code == 204
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_address"] == f"{owner_username}@collabrains.eu"


async def test_webhook_ignores_unrecognized_event_types(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")

    event = _stripe_event("customer.updated", {"id": "cus_irrelevant"})
    with patch("api.billing_router.construct_webhook_event", return_value=event):
        response = await client.post(
            "/billing/webhook", content=b"{}", headers={"stripe-signature": "whatever"}
        )
    assert response.status_code == 204
