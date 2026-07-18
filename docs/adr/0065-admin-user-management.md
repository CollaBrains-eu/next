# 0065 — Admin user-management: role, password, deactivate, phone

## Status

Accepted

## Context

A feature-parity audit against the reference Codeberg `Cbrains-v2`
implementation (`admin.py` / `AdminPage.tsx`) found that the Admin
Dashboard's Users tab was read-only beyond creation: once a user
existed, there was no way to change their role, reset their password,
revoke their access, or change the Signal phone number linked to their
account. v2 had all four as per-row actions. Confirmed live on
production (`/admin` → Users tab: a plain table, no per-row actions) and
in `services/api/src/api/admin_router.py` (only create/list/resend-welcome
existed for users).

Full design brainstorming and the resulting decisions live in
`docs/superpowers/specs/2026-07-18-admin-user-management-design.md`; the
13-task TDD implementation plan is
`docs/superpowers/plans/2026-07-18-admin-user-management.md`. This ADR
records what actually shipped.

v2's `beta_granted` / `passkey_required` / `signal_upload_allowed` /
`app_upload_allowed` toggles were deliberately **not** ported — no
equivalent authorization concept exists in the current product, and
porting them would mean designing new concepts, not porting a UI.

## Decision

**Data model**: `users.is_active: bool` (new migration, chained onto
head `d3f8a1c6b9e4`, additive with `server_default=true`). Deactivation
is a *soft* revoke, not a hard delete — `owner_id`/`user_id`/`created_by`
are `NOT NULL` FKs to `users.id` on documents, cases, tasks, and
entities, so a hard Postgres delete would violate those constraints or
require reassigning content, which is out of scope. Removing the LDAP
entry is what actually matters for access control, since LDAP bind is
the only authentication path in this stack.

**Backend** (`services/api/src/api/ldap_auth.py`,
`services/api/src/api/admin_router.py`):
- `ldap_auth.set_password` / `ldap_auth.delete_user` — two new
  admin-bind functions mirroring the existing `create_user` pattern
  (bind as `cn=admin,{base_dn}`, `unbind()` in `finally`). `delete_user`
  raises `LdapAdminError` with `"does not exist"` in the message when
  the entry is already gone, which callers treat as idempotent success.
- `PUT /admin/users/{id}/role` — Postgres-only (`role` was already
  documented as Postgres-only post-provisioning); 404 unknown user, 403
  on the `service` role.
- `PUT /admin/users/{id}/password` — LDAP admin-bind reset, returns the
  same `AdminUserCreated` shape as user creation (temp password shown
  once, never logged).
- `DELETE /admin/users/{id}` — LDAP delete (idempotent) + Postgres
  `is_active = false`; never deletes or reassigns owned content.
- `PUT /admin/users/{id}/phone` — reuses the existing
  `validate_phone_number` and duplicate-phone uniqueness check already
  used by self-service linking and admin create-user.
- `get_current_user` (`auth.py`) now rejects with 401 when
  `is_active is False`, on top of the existing invalid/expired-token
  check. This closes the gap between "LDAP entry deleted" and "their
  existing JWT hasn't technically expired yet" — deactivation takes
  effect on the user's *very next request*, confirmed live (see
  Verification).
- `get_effective_user` (`auth.py`, ADR 0006) — the signal-bot
  on-behalf-of-phone attribution path — also rejects a linked user whose
  `is_active` is `False`, closing the same gap on the Signal channel
  as `get_current_user` closes for the JWT path. Found during this
  feature's own code review (not part of the original plan/spec, since
  it lives in pre-existing ADR-0006 code the plan never touched) and
  fixed the same day rather than deferred, since deactivation is
  meaningless if one of its two attribution paths still works.

**Frontend** (`apps/web/src/routes/AdminDashboard.tsx`):
- Each non-service row gets a `Dropdown`-based row-action menu: role
  toggle (inline, optimistic update), set phone (inline expanding
  field), reset password (opens the shared one-time-password card),
  deactivate (`Modal` confirm step).
- `TempPasswordCard` (new, `apps/web/src/components/`) extracts the
  one-time-password display markup that was previously inline only in
  the create-user flow, now shared between create-user and
  reset-password rather than duplicated.
- Deactivated rows render a "Deactivated" badge next to the role badge
  and lose their action menu, rather than disappearing — an admin can
  still see who used to have access.

## Verification

Executed via Subagent-Driven Development: two file-disjoint tracks
(backend: migration/`ldap_auth`/`admin_router`/`auth.py`; frontend:
`api.ts`/`AdminDashboard.tsx`/locales) run as concurrent, internally
sequential subagent chains sharing one checkout (no worktree isolation
— commits interleave on `main`, but the tracks touch disjoint files so
this caused no conflicts).

- Backend: 6/6 new endpoint tests + the `is_active`-rejection test
  passing in isolation; full suite run showed 28 pre-existing failures
  unrelated to this work (confirmed via `git diff` against the
  pre-session base commit — the failing test bodies are byte-for-byte
  unchanged, and the failures reproduce deterministically file-in-isolation,
  spanning entities/appointments/AI-gateway/tasks — a known class of
  test-DB pollution from tests sharing one live Postgres, wider than
  the two failures ADR 0061 had previously documented but not caused by
  this session's changes).
- Frontend: 68/68 files, 356/356 tests passing (up from the 346
  baseline); `tsc --noEmit` shows 373 pre-existing errors, all
  `toBeInTheDocument`/`toHaveTextContent`-not-found on `.test.tsx`
  files project-wide (a jest-dom type-declaration gap in the `tsc`
  config, not real type errors — `vitest run` exercises and passes
  every one of those assertions at runtime).
- Rebuilt and redeployed the `api` image, ran `alembic upgrade head`
  (no-op, already applied), restarted `api`, built the frontend
  (`vite build`).
- Live-browser verification against two disposable test accounts
  (LDAP-created directly, not through a real admin's credentials):
  role change (instant, no reload), set phone (set and clear), reset
  password (shared card, correct one-time value), deactivate (confirm
  dialog copy matches spec, row badges correctly, action menu
  disappears). **Critical check**: captured the target test user's JWT
  before deactivating; the same still-unexpired JWT was rejected with
  401 on the very next request immediately after deactivation via the
  live admin UI — proving the `is_active` check works against the real
  stack, not just the test suite. No console errors. Both disposable
  accounts deleted (LDAP + Postgres) afterward.

## Consequences

- Admin user-management now has parity with v2 for the four actions
  that map to real current-product concepts; the toggles that don't
  (beta/passkey/upload-permission flags) remain deliberately unported.
- The wider pre-existing test-DB-pollution issue (28 failures, not 2) is
  now documented at its current true scope; a follow-up to give the
  backend suite per-test transaction isolation would eliminate this
  class of failure but is out of scope here.
- `is_active` becomes a second gate alongside `role` on every
  authenticated request, following the same "Postgres is the
  authorization source of truth" model `auth.py` already documented for
  `role`.
