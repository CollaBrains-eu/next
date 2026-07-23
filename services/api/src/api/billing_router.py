"""Stripe billing endpoints (Priority 3 commercial SaaS, ADR 0074).

Checkout/portal creation is gated the same way organizations_router.py
gates org management (organizations.require_org_admin) -- billing is an
org-level concern, not a per-member one. /billing/subscription is
readable by any member (so a non-admin teammate can at least see the
plan they're on). /billing/webhook is the one public endpoint here,
authenticated by Stripe's own signature header instead of a bearer
token, same as any inbound webhook.
"""
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.billing_service import (
    BillingNotConfigured,
    construct_webhook_event,
    create_billing_portal_session,
    create_checkout_session,
    get_or_create_subscription_row,
    handle_webhook_event,
)
from api.config import settings
from api.db import get_db
from api.models import Organization, User
from api.organizations import get_organization_for_user, require_org_admin

router = APIRouter(prefix="/billing", tags=["billing"])


async def _get_org_or_404(db: AsyncSession, current_user: User) -> Organization:
    organization = await get_organization_for_user(db, current_user.id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


class CheckoutSessionIn(BaseModel):
    plan: str


class UrlOut(BaseModel):
    url: str


@router.post("/checkout-session", response_model=UrlOut)
async def create_checkout(
    body: CheckoutSessionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UrlOut:
    organization = await _get_org_or_404(db, current_user)
    require_org_admin(current_user, organization)

    try:
        url = await create_checkout_session(
            db,
            organization=organization,
            plan=body.plan,
            success_url=f"{settings.app_base_url}/settings?billing=success",
            cancel_url=f"{settings.app_base_url}/settings?billing=cancelled",
        )
    except BillingNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UrlOut(url=url)


@router.post("/portal-session", response_model=UrlOut)
async def create_portal(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UrlOut:
    organization = await _get_org_or_404(db, current_user)
    require_org_admin(current_user, organization)

    try:
        url = await create_billing_portal_session(
            db, organization=organization, return_url=f"{settings.app_base_url}/settings"
        )
    except BillingNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return UrlOut(url=url)


class SubscriptionOut(BaseModel):
    plan: str | None
    status: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionOut:
    organization = await _get_org_or_404(db, current_user)
    subscription = await get_or_create_subscription_row(db, organization_id=organization.id)
    return SubscriptionOut(
        plan=subscription.plan,
        status=subscription.status,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
    )


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> None:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = construct_webhook_event(payload=payload, signature_header=signature)
    except BillingNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except (stripe.error.SignatureVerificationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload or signature"
        ) from exc

    await handle_webhook_event(db, event)
