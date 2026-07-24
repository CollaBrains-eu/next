# Stripe Billing — Real End-to-End Verification

## Status

Approved (brainstorming). Closes the last open item from ADR 0074's
roadmap (item 3): billing code was built and unit-tested with mocks,
but real verification against Stripe was explicitly deferred pending a
test-mode secret key.

## Problem

`billing_router.py` / `billing_service.py` (live on collabrains.eu
since PR #111, reachable since PR #117 fixed the missing `/billing`
Caddy prefix) implement checkout, billing-portal, and webhook handling
for Stripe subscriptions, but have never been exercised against a real
Stripe account. Three things are missing before that's possible:

1. `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` — now provided (test
   mode).
2. `STRIPE_PRICE_ID_STARTER` / `STRIPE_PRICE_ID_PRO` — no test-mode
   Products/Prices exist yet for the advertised €5/mo and €12/mo tiers
   (`Landing.tsx`, `en.json`).
3. `STRIPE_WEBHOOK_SECRET` — no webhook endpoint is registered in
   Stripe yet.

`STRIPE_PUBLISHABLE_KEY` is confirmed unused/dead in the current code
(checkout is Stripe-hosted-Checkout via redirect, not Stripe.js/
Elements) — configured for completeness, not exercised by this task.

## Approach

**1. Stripe-side setup**, via the Stripe API using the provided secret
key (test mode only, no dashboard clicking):
- Create two test-mode Products+Prices: Starter (€5/month recurring),
  Pro (€12/month recurring).
- Register a webhook endpoint at `https://collabrains.eu/billing/webhook`
  subscribed to exactly the event types `billing_service.py` already
  handles: `checkout.session.completed`,
  `customer.subscription.{created,updated,deleted}`,
  `invoice.payment_failed`.

**2. Server config** (178.254.22.178, `/opt/collabrains/.env`):
- Add the 5 `STRIPE_*` values. Not committed, not logged.
- `docker compose restart api` — env-only change, no rebuild.

**3. Live verification**, disposable test org/user, same
create-verify-delete discipline as every prior live-test pass (P1/P2):
- Checkout for Starter with Stripe test card `4242 4242 4242 4242` →
  confirm redirect succeeds and the `subscriptions` row updates to
  `plan=starter/status=active` via webhook.
- Open a billing portal session → confirm it loads.
- Simulate an upgrade to Pro → confirm the row updates.
- Simulate `invoice.payment_failed` → confirm the failure-email code
  path fires.
- Cancel the test subscription → confirm `status=canceled` after
  `customer.subscription.deleted`.

**4. Cleanup**: cancel/delete the test Stripe customer+subscription
(the Products/Prices/webhook endpoint stay — permanent test-mode
config going forward); delete the disposable Postgres test user/org
rows.

## Error handling

- Webhook signature failures already return 400
  (`stripe.error.SignatureVerificationError` in `billing_router.py`) —
  checked via server logs during setup rather than assumed correct.
- A rejected/malformed secret key fails immediately at Product/Price
  creation, before the server is touched.

## Testing / definition of done

- Real HTTP checkout completes against Stripe test mode.
- `subscriptions` table reflects correct plan/status/period-end after
  each webhook event, confirmed via direct DB query — not just "the
  UI looks right".
- No application code changes. `test_billing.py`'s existing mocked
  coverage is unchanged; this task proves the real integration point
  mocks can't.

## Out of scope

- `STRIPE_PUBLISHABLE_KEY` usage — dead code, not this task.
- Live/production-mode Stripe.
- New automated tests.
