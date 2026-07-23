# 0074 — Commercial SaaS gap analysis and roadmap

## Status

Gap analysis complete. Implementation starting on this branch
(`feat-priority-3-commercial-saas`), small PR(s), no auto-merge/deploy this
phase (explicit instruction — differs from Priority 2's deploy authorization).

## Context

ADR 0066 already covered architecture/security/testing/performance/a11y and
scored SaaS readiness; it flagged billing and multi-tenancy as real gaps but
deliberately deferred them ("should start from their own brainstormed spec").
This ADR is that spec: a focused survey of everything needed to let a
stranger discover, sign up for, pay for, and self-administer CollaBrains
without any of our own manual intervention — the dimensions ADR 0066 named
but didn't depth-audit (onboarding, invitations, billing, account/org
settings, marketing, legal, support, analytics).

Method: one read-only survey grounded in file:line citations, explicitly
scoped to skip anything ADR 0066 already covered.

## Findings

### 1. Auth / signup

No public signup exists. Account creation is LDAP-admin-only
(`admin_router.py:352`); the Postgres `User` row is provisioned on first LDAP
login (`auth.py:75-99`). Email-sending infrastructure already exists
(`email_client.py`, SMTP, best-effort no-op if unconfigured) but only powers
the admin-created-user welcome flow (`onboarding_service.py`,
`OnboardingToken` model) — there's no self-registration, so no
"verify your email" flow either. No self-service password reset — only an
admin-bind reset via the Admin Dashboard (`admin_router.py:539`).

**This is the hard blocker**: nothing downstream (checkout, invitations,
trials) works if a stranger cannot create their own account today.

### 2. Organizations & invitations

`Organization` (`models.py:18-36`) is name + a JSONB policy blob; every user
defaults into one `DEFAULT_ORGANIZATION_ID`. No `Membership`/`Invitation`
model tied to `Organization` exists, and `organizations_router.py` has no
add/remove/invite-member endpoint at all — only rename, policy-edit, and a
read-only member list.

Three separate, narrower invite mechanisms exist instead — case sharing
(`cases_router.py`), workspace sharing (`workspace_router.py`), and token
share-links (`sharing_router.py`) — and **all three require the invitee to
already be a provisioned platform user**. There is no "invite a stranger by
email into my org" flow anywhere, which is the second hard blocker for
self-service teams.

### 3. Billing / payments

Confirmed absent repo-wide (checked, not just grepped-and-assumed:
`plans_router` is the AI task-planning feature, unrelated to pricing tiers).
**But the frontend already promises pricing** — `Landing.tsx:219-266` and
`en.json:657-698` show three real tiers (Early/Starter €5/Pro €12/Enterprise)
whose CTAs all just call `goToLogin()`. This is a live, shipped
overpromise: a visitor can read prices today and hit a wall with no way to
actually buy. Closing this gap is as much a trust issue as a revenue one.

### 4. Account / organization settings

`Settings.tsx` has prefs, passkeys, address history, a read-only org member
list, and workspace sharing — no add-member UI, no user-profile editor
(name/email), no password-change UI, no billing/plan section anywhere.
`AdminDashboard.tsx` is a platform-wide LDAP console, not per-org
self-service settings.

### 5. Marketing pages

One real landing page (`Landing.tsx`) with pricing as inline scroll sections,
public at `/`. No dedicated `/pricing`, `/about`, `/features`.

### 6. Legal pages

**None exist.** No Privacy Policy, Terms of Service, or cookie-consent
anywhere (`Legal.tsx` is the AI legal-drafting *product feature*, a false
positive on the filename). Real policy text is a legal decision, not an
engineering one — flagged as a stop-condition item below, not something this
phase writes unilaterally.

### 7. Support / docs / help

None: no help center, changelog, FAQ, or contact form. Only affordance is a
plain `mailto:` link on the Enterprise pricing card.

### 8. Analytics

None: no product-analytics SDK (PostHog/Mixpanel/GA/Plausible) anywhere.
Sentry is present but deliberately scoped to errors only, PII stripped.

### 9. Developer platform

`packages/sdk` is still a README-only stub, matching ADR 0066. Not a blocker
for launch; parked.

### 10. Roles

A single global `User.role` (`member`/`admin`/`service`) doubles as both
platform-admin and org-admin (`organizations_router.py`'s own docstring
admits this). Case/workspace ownership are two more independent,
non-unified authorization concepts. Good enough for "one org invites
teammates with a member/admin role" — not good enough for real RBAC, which
stays out of scope for this phase (ADR 0066 Priority 4, still future work).

## Decision — prioritized roadmap

Ordered by hard dependency, not by the phase numbering in the original
request (billing self-service literally cannot exist before signup exists):

| # | Item | Depends on | Effort | Notes |
|---|---|---|---|---|
| 1 | Self-service signup + email verification | — | M | Reuses `email_client.py`, LDAP `create_user()` |
| 2 | Org invitations by email (new user or existing) | #1 | M | New `Invitation` model; unifies the "invite a stranger" gap |
| 3 | Stripe billing (checkout, portal, webhooks, plan gating) | #1 | M/L | **Needs a Stripe test-mode key from the user to verify end-to-end**; code/tests/migration can be built and mocked without it |
| 4 | Account/org settings expansion (profile edit, member mgmt UI, billing UI) | #1–3 | M | Fills the Settings.tsx gaps found above |
| 5 | Legal pages (Privacy/Terms/Cookie) | — | S (eng) | **Placeholder content only — real policy text is a legal decision, flagged not written** |
| 6 | Pricing page reconciliation (wire existing tiers to real checkout) | #3 | S | Landing.tsx already has the copy |
| 7 | Support/help/changelog surface | — | S | Lowest urgency; last |
| 8 | Analytics (product usage, conversion funnel) | — | S | Pick a privacy-respecting option consistent with existing Sentry stance |

Multi-tenant RBAC 2.0 and a developer SDK remain explicitly out of scope
(ADR 0066 Priority 4) — not needed to sell a single-org-per-customer plan,
which is what the existing pricing tiers describe anyway.

Execution rules for this phase (per explicit instruction, superseding the
auto-merge/auto-deploy authorization given for Priority 2): small commits,
tests after every logical change, feature branch + PR only, no auto-merge,
no auto-deploy, no direct push to `main`. Stop only for a business decision,
a legal decision, payment-provider credentials, or phase completion.

## Consequences

Items 1–2 unlock every later item and are being implemented first. Item 3's
code lands regardless of credential availability (mocked in tests, same
pattern already used for Ollama/RDW integrations in this codebase); real
end-to-end verification against Stripe waits on a test-mode secret key.
Item 5's actual legal text is intentionally left as a TODO placeholder, not
invented, and is called out explicitly in the final report rather than
silently shipped.
