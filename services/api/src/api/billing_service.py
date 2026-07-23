"""Stripe billing (Priority 3 commercial SaaS, ADR 0074).

Subscription rows are entirely webhook-driven -- create_checkout_session
and create_billing_portal_session only ever read/create a
stripe_customer_id, never write plan/status directly; that mapping lives
in exactly one place (_handle_subscription_updated) so it can't drift
from what Stripe itself believes is true.

Stays inert until STRIPE_SECRET_KEY is configured (BillingNotConfigured,
mapped to a 503 by billing_router.py) -- same "no key means no calls"
contract email_client.py/sentry_config.py already use, rather than
failing at import time when this module is merely loaded in a test/dev
environment with no Stripe account behind it.
"""
from datetime import datetime, timezone
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.email_client import send_email
from api.models import Organization, Subscription, User


class BillingNotConfigured(Exception):
    """Raised when Stripe isn't configured (no secret key, or no webhook
    secret for signature verification)."""


def _require_configured() -> None:
    if not settings.stripe_secret_key:
        raise BillingNotConfigured("Stripe is not configured (STRIPE_SECRET_KEY is empty)")
    stripe.api_key = settings.stripe_secret_key


def _price_id_for_plan(plan: str) -> str | None:
    return {"starter": settings.stripe_price_id_starter, "pro": settings.stripe_price_id_pro}.get(plan)


def _plan_for_price_id(price_id: str | None) -> str | None:
    if not price_id:
        return None
    if price_id == settings.stripe_price_id_starter:
        return "starter"
    if price_id == settings.stripe_price_id_pro:
        return "pro"
    return None


async def get_or_create_subscription_row(db: AsyncSession, *, organization_id: UUID) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.organization_id == organization_id))
    subscription = result.scalar_one_or_none()
    if subscription is None:
        subscription = Subscription(organization_id=organization_id)
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
    return subscription


async def _get_subscription_row_by_customer_id(db: AsyncSession, *, customer_id: str) -> Subscription | None:
    result = await db.execute(select(Subscription).where(Subscription.stripe_customer_id == customer_id))
    return result.scalar_one_or_none()


async def _get_or_create_stripe_customer(db: AsyncSession, *, organization: Organization) -> str:
    _require_configured()
    subscription = await get_or_create_subscription_row(db, organization_id=organization.id)
    if subscription.stripe_customer_id:
        return subscription.stripe_customer_id

    owner_email = None
    if organization.owner_user_id is not None:
        owner = await db.get(User, organization.owner_user_id)
        owner_email = owner.email if owner is not None else None

    customer = stripe.Customer.create(
        name=organization.name, email=owner_email, metadata={"organization_id": str(organization.id)}
    )
    subscription.stripe_customer_id = customer.id
    await db.commit()
    return customer.id


async def create_checkout_session(
    db: AsyncSession, *, organization: Organization, plan: str, success_url: str, cancel_url: str
) -> str:
    """Returns the Stripe-hosted checkout URL to redirect the browser to."""
    _require_configured()
    price_id = _price_id_for_plan(plan)
    if not price_id:
        raise ValueError(f"unknown or unconfigured plan: {plan!r}")

    customer_id = await _get_or_create_stripe_customer(db, organization=organization)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=str(organization.id),
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url


async def create_billing_portal_session(db: AsyncSession, *, organization: Organization, return_url: str) -> str:
    _require_configured()
    customer_id = await _get_or_create_stripe_customer(db, organization=organization)
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return session.url


def construct_webhook_event(*, payload: bytes, signature_header: str) -> stripe.Event:
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise BillingNotConfigured("Stripe webhook is not configured")
    stripe.api_key = settings.stripe_secret_key
    return stripe.Webhook.construct_event(payload, signature_header, settings.stripe_webhook_secret)


async def _handle_checkout_completed(db: AsyncSession, session: dict) -> None:
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    if not customer_id or not subscription_id:
        return

    subscription_row = await _get_subscription_row_by_customer_id(db, customer_id=customer_id)
    if subscription_row is None:
        org_id = session.get("client_reference_id")
        if not org_id:
            return
        subscription_row = await get_or_create_subscription_row(db, organization_id=UUID(org_id))
        subscription_row.stripe_customer_id = customer_id

    subscription_row.stripe_subscription_id = subscription_id
    await db.commit()
    # plan/status/current_period_end land via the customer.subscription.created
    # (or .updated) event Stripe sends alongside this one -- not duplicated
    # here, so exactly one handler (_handle_subscription_updated) owns that
    # mapping and it can't drift between two write paths.


def _plan_and_status_from_stripe_subscription(subscription: dict) -> tuple[str | None, str]:
    items = subscription.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    return _plan_for_price_id(price_id), subscription["status"]


async def _handle_subscription_updated(db: AsyncSession, subscription: dict) -> None:
    customer_id = subscription.get("customer")
    if not customer_id:
        return
    subscription_row = await _get_subscription_row_by_customer_id(db, customer_id=customer_id)
    if subscription_row is None:
        return

    plan, status_value = _plan_and_status_from_stripe_subscription(subscription)
    subscription_row.stripe_subscription_id = subscription["id"]
    subscription_row.plan = plan
    subscription_row.status = status_value
    subscription_row.cancel_at_period_end = bool(subscription.get("cancel_at_period_end", False))
    period_end = subscription.get("current_period_end")
    if period_end is not None:
        subscription_row.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
    await db.commit()


async def _handle_subscription_deleted(db: AsyncSession, subscription: dict) -> None:
    customer_id = subscription.get("customer")
    if not customer_id:
        return
    subscription_row = await _get_subscription_row_by_customer_id(db, customer_id=customer_id)
    if subscription_row is None:
        return
    subscription_row.status = "canceled"
    await db.commit()


def _payment_failed_text(*, organization_name: str) -> str:
    return (
        f"De betaling voor het abonnement van {organization_name} op CollaBrains is mislukt.\n\n"
        "Werk je betaalgegevens bij via de facturering-instellingen om onderbreking van je "
        "abonnement te voorkomen.\n\nMet vriendelijke groet,\nCollaBrains"
    )


def _payment_failed_html(*, organization_name: str) -> str:
    return (
        f"<p>De betaling voor het abonnement van <strong>{organization_name}</strong> op CollaBrains "
        "is mislukt.</p>"
        "<p>Werk je betaalgegevens bij via de facturering-instellingen om onderbreking van je "
        "abonnement te voorkomen.</p>"
        "<p>Met vriendelijke groet,<br>CollaBrains</p>"
    )


async def _handle_payment_failed(db: AsyncSession, invoice: dict) -> None:
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    subscription_row = await _get_subscription_row_by_customer_id(db, customer_id=customer_id)
    if subscription_row is None:
        return

    organization = await db.get(Organization, subscription_row.organization_id)
    if organization is None or organization.owner_user_id is None:
        return
    owner = await db.get(User, organization.owner_user_id)
    if owner is None or not owner.email:
        return

    await send_email(
        to_address=owner.email,
        subject="Betaling mislukt voor je CollaBrains-abonnement",
        html_body=_payment_failed_html(organization_name=organization.name),
        text_body=_payment_failed_text(organization_name=organization.name),
    )


async def handle_webhook_event(db: AsyncSession, event: stripe.Event) -> None:
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(db, data)
    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        await _handle_subscription_updated(db, data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(db, data)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(db, data)
    # Every other event type is intentionally ignored, not an error --
    # Stripe sends far more event types than this app acts on, and erroring
    # on an unrecognized-but-harmless one would just make Stripe retry it
    # forever.
