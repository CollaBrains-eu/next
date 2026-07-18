# Admin user-management (role, password, deactivate, phone) — Design

## Status

Approved (brainstormed 2026-07-18)

## Context

A parity audit against the reference v2 implementation (`admin.py` /
`AdminPage.tsx` in the Codeberg `Cbrains-v2` checkout) found that the
current Admin Dashboard's Users tab is read-only beyond creation: once a
user exists there is no way to change their role, reset their password,
revoke their access, or change the Signal phone linked to their account.
v2 had all four as per-row actions. Confirmed live on production
(`/admin` → Users tab: a plain table, no per-row actions) and in
`services/api/src/api/admin_router.py` (487 lines: only
create/list/resend-welcome for users).

## Goals

1. Admins can change a user's role (`member` ⇄ `admin`).
2. Admins can reset a user's password (one-time generated temp password,
   same UX as the existing create-user flow).
3. Admins can deactivate a user: revokes LDAP login and immediately
   invalidates any live session, while their created content (documents,
   cases, tasks, entities) stays fully intact and attributed to them.
4. Admins can set or clear the Signal phone number linked to a user's
   account (an override of the existing self-service `/auth/me/phone`).

## Non-goals

- `beta_granted` / `passkey_required` / `signal_upload_allowed` /
  `app_upload_allowed` toggles from v2 — no equivalent concept exists in
  the current product (there's real passkey auth, but no per-user
  "require it" policy; there's no per-channel upload permission system).
  Porting these would mean designing new authorization concepts, not
  porting a UI. Deferred until/unless the user asks for them specifically.
- The Admin Settings tab (AI defaults, `apply-all`) and Docs/guide tab —
  separate scope from user-management, not part of this pass.
- A generic admin-action audit-log viewer — v2 wrote to a log but never
  exposed a UI for it either, and no `audit_log` table exists today
  (only the unrelated `ai_call_log`). Easy to add later; not blocking
  this feature.
- `users/suggest-username` and `start-onboarding` from v2 — creation-time
  UX, not management of *existing* users; the existing `resend-welcome`
  endpoint already covers the overlapping need.
- Reassigning or hard-deleting a user's owned content on removal — out of
  scope; deactivation preserves everything by design (see below).

## Backend

### Data model

`services/api/src/api/models.py` — `User` gains one column:

```python
is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
```

New Alembic revision, chained onto the current head, additive (backfills
`true` for every existing row) — same safe-migration shape as ADR 0064's
`tasks` columns.

**Why deactivate instead of delete**: `owner_id`/`user_id`/`created_by`
are `NOT NULL` foreign keys to `users.id` on documents, cases, tasks, and
entities. A hard Postgres delete would violate those constraints (or
require reassigning/orphaning a user's content, which is out of scope).
Removing the LDAP entry is what actually matters for access control —
LDAP bind is the only way to authenticate in this stack.

### `services/api/src/api/ldap_auth.py`

Two new functions, same admin-bind pattern as the existing `create_user`
(bind as `cn=admin,{base_dn}`, `unbind()` in `finally`):

```python
def set_password(*, username: str) -> str:
    """Admin-bind password reset. Generates a fresh temporary password
    (never admin-typed — avoids weak/guessable admin-chosen passwords,
    matches create_user's existing UX) and modifies userPassword.
    Returns the new password once. Raises LdapAdminError if the user
    doesn't exist or the modify fails."""

def delete_user(*, username: str) -> None:
    """Admin-bind LDAP entry delete. Raises LdapAdminError (with
    "does not exist" in the message, mirroring create_user's own
    "already exists" convention) if there's no such entry, or on any
    other directory-reported failure. Does not touch Postgres --
    callers pair this with User.is_active = False."""
```

### `services/api/src/api/admin_router.py`

New endpoints, all behind the existing `_require_admin(current_user)`
guard used by every other admin route:

- **`PUT /users/{user_id}/role`** — body `{role: Literal["member", "admin"]}`.
  404 if the user doesn't exist, 403 if their current role is `"service"`
  (refuses to touch the signal-bot account, matching v2's own guard on
  delete). Otherwise updates `User.role` directly in Postgres and
  commits — no LDAP write, since `auth.py` already documents role as
  Postgres-only after first-login provisioning.
- **`PUT /users/{user_id}/password`** — no body. 404/403 as above. Calls
  `ldap_auth.set_password(username=user.username)`, returns the existing
  `AdminUserCreated` shape (`{username, temporary_password}`).
- **`DELETE /users/{user_id}`** — 404/403 as above. Calls
  `ldap_auth.delete_user(...)`; if it raises with "does not exist" (entry
  already gone, e.g. a retried request after a partial prior failure),
  treat that as success rather than erroring, same tolerance
  `admin_create_user` already applies to its own LDAP error string.
  Then sets `User.is_active = False`, commits, returns 204.
- **`PUT /users/{user_id}/phone`** — body `{phone_number: str | None}`.
  404 if missing. `None`/empty clears the link. Otherwise reuses
  `validate_phone_number` plus the same uniqueness check already used in
  `admin_create_user` and self-service `/auth/me/phone` (409 if the
  number is linked to a different account).

### `services/api/src/api/auth.py`

`get_current_user` already loads the `User` row per request (to read
`role`). It gains one check: if `is_active is False`, reject with 401,
same as an invalid/expired token. This makes deactivation take effect on
the user's *very next request*, not just block future logins — closing
the gap between "LDAP entry deleted" and "their existing JWT hasn't
technically expired yet."

### `AdminUserOut`

Gains `is_active: bool` so the frontend can render deactivated rows
distinctly instead of just disappearing them.

## Frontend

`apps/web/src/routes/AdminDashboard.tsx`, Users tab:

- Each row gets a row-action menu built on the existing
  `components/ui/Dropdown` primitive (no new component): "Change role",
  "Reset password", "Set phone", "Deactivate". The trigger is hidden for
  `role === "service"` rows.
- **Change role**: an inline two-option control (not a modal) that PUTs
  immediately and optimistically updates the row; reverts with an inline
  error on failure.
- **Reset password**: opens the *same* one-time-password modal already
  built for create-user (`data-testid="temp-password"`, the
  `admin.tempPasswordHint` copy) — extract it into a small shared
  component if it isn't already, rather than duplicating the markup.
- **Set phone**: an inline expanding field in the row (not a popover —
  no popover primitive exists yet in this kit) with a save button,
  reusing the phone-validation error display already used for
  self-service phone linking.
- **Deactivate**: a `components/ui/Modal` confirm step — "Deactivate
  {display_name}? They will be signed out immediately and can no longer
  log in. Their documents and cases are kept." On confirm, calls the
  `DELETE` endpoint and marks the row deactivated (grayed out, actions
  disabled) rather than removing it from the list, so an admin can still
  see who used to have access.

`apps/web/src/lib/api.ts` — four new client functions (`setUserRole`,
`resetUserPassword`, `deactivateUser`, `setUserPhone`), and `is_active`
added to the `AdminUserOut` type.

## Testing

- `ldap_auth` unit tests for `set_password`/`delete_user`, mocking
  `ldap3.Connection` the same way the existing `create_user` tests do.
- `test_admin_router.py`: one test per new endpoint — success path, 404
  (unknown user), 403 (service account); the phone endpoint's existing
  409-duplicate case reused for the admin-override path too.
- Wherever `get_current_user` is already tested (`auth.py`'s test file)
  gains one case: a deactivated user's still-unexpired JWT is rejected.
- `AdminDashboard.test.tsx` extended per new row action: role change,
  password-reset (reuses the existing create-user modal test), deactivate
  confirm-then-disable, phone set/clear + duplicate-phone error.
- Full suite (`pytest` + `pnpm vitest run`) green, then a live-browser
  pass on `/admin`'s Users tab against a disposable test user exercising
  all four actions — including confirming a deactivated test user's
  existing JWT is actually rejected on its next request, not just that
  fresh login fails. Test user torn down afterward, same cleanup
  discipline as every other phase's live testing.

## Open questions resolved during brainstorming

- **Delete semantics**: deactivate (LDAP delete + Postgres
  `is_active=false`), not a hard Postgres delete — the `NOT NULL` owner
  FKs on documents/cases/tasks/entities make hard delete unsafe, and
  reassigning/orphaning content is out of scope.
- **Password reset UX**: admin triggers a generated one-time temp
  password (matches `create_user`'s existing pattern) rather than typing
  an arbitrary password themselves (v2's approach) — avoids weak or
  guessable admin-chosen passwords.
- **Role values**: only `member ⇄ admin` are admin-settable; `service`
  is refused both as a target role and as a row this UI acts on at all.
- **v2 toggles not ported**: `beta_granted`/`passkey_required`/
  `signal_upload_allowed`/`app_upload_allowed` have no current-product
  equivalent and are deferred rather than blindly ported.
