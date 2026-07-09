# 0048 — Admin: add users (LDAP write path)

## Status

Accepted

## Context

Users have only ever come into existence via LDAP auto-provisioning on
first successful login (`api.auth._get_or_provision_user`) — there was
no way for an admin to create an account ahead of time. `ldap_auth.py`
only ever bound to the directory *as the user being authenticated*; the
`LDAP_ADMIN_PASSWORD` credential already existed in the compose config
(bound to the `openldap` container's bootstrap) but was never passed to
the `api` service or used for anything.

## Decision

- `ldap_auth.py` gains `create_user()`, binding as `cn=admin,{base_dn}`
  (admin bind, distinct from the existing user-bind `authenticate()`).
  Computes the next `uidNumber`/`gidNumber` by scanning existing
  `posixAccount` entries under `ou=people` and taking `max + 1` (matches
  the bootstrap LDIF's `10001`, `10002` sequence). Generates a random
  temporary password (`secrets.token_urlsafe(12)`), SSHA-hashes it via
  `ldap3.utils.hashed.hashed`, creates the `inetOrgPerson` +
  `posixAccount` + `shadowAccount` entry, and — if `is_admin` — adds the
  new DN to the admin group via `MODIFY_ADD`. Raises `LdapAdminError` on
  any failure (bind failure, duplicate entry, group-add failure after
  the user entry already exists).
- The temporary password is returned once and never stored or logged —
  there's no email-delivery mechanism, so the admin relays it out of
  band. This is the same "smallest safe slice" choice made throughout
  this project: build the capability, not a notification system nobody
  asked for yet.
- **The Postgres `User` row is deliberately NOT created by this
  endpoint.** It appears the same way it always has — on the new user's
  first successful login, via the existing auto-provision path. This
  keeps `create_user` a pure LDAP-directory operation and avoids two
  divergent "how does a User row come to exist" code paths.
- New `POST /admin/users` (`admin_router.py`), admin-only via the
  existing `_require_admin` pattern. Maps `LdapAdminError` to `409`
  when the message mentions "already exists", `502` otherwise (LDAP
  reachability issues) — same status-code convention as
  `vehicles_router.py`'s RDW-outage handling (ADR 0046).
- `config.py` gains `ldap_admin_password`; `docker-compose.yml`'s `api`
  service environment gains `LDAP_ADMIN_PASSWORD: ${LDAP_ADMIN_PASSWORD}`
  — previously only the `openldap` service itself received this
  variable. This required recreating the live `api` container
  (`docker compose up -d api`), not just a code hot-reload, since
  environment variables are injected at container start.
- Frontend: `AdminDashboard.tsx` gains a "Users" tab — an "Add user"
  button opens a `Modal` form (username, display name, email, admin
  checkbox); on success, the temporary password is shown once in a
  dismissible card with a copy-friendly `<code>` block, then the modal
  closes. Reuses the existing `Modal` primitive, no new component built.

## Verification

- New tests in `test_admin_router.py`: non-admin gets `403`; admin
  create returns the username + temp password and calls the LDAP layer
  with the right arguments; duplicate username → `409`; LDAP-bind
  failure → `502`.
- **Real end-to-end verification against the live LDAP directory**
  (not just mocked tests, since this is the first LDAP-write code path
  in the project): created a real user via `create_user()` in an
  isolated throwaway container pointed at the live `openldap` service;
  confirmed via `ldapsearch` the entry has the right attributes and the
  correct next `uidNumber` (`10003`, after the bootstrap's `10001`/
  `10002`); **logged in with the generated temporary password through
  the real `/auth/token` endpoint and got a valid JWT back**; confirmed
  a second `create_user()` call for the same username raises
  `LdapAdminError("entryAlreadyExists")`. Test user and its
  auto-provisioned Postgres row were deleted afterward.
- Full backend suite (isolated container): 336 passed, 14 failed —
  exact known baseline, zero new failures.
- Full frontend suite (live `web` container): 47 files / 204 tests
  passed, including the new `AdminDashboard.test.tsx` (4 tests: opens
  the form, successful create shows the password, failure keeps the
  form open with an error, dismissing the password card).
- Production bundle rebuilt; site returns `200`.

## Consequences

- `LDAP_ADMIN_PASSWORD`'s actual live value is still the placeholder
  `changeme` from `.env.example` — this admin-write capability makes
  that specific credential more consequential than it was before (it
  can now create accounts, including admin accounts, not just serve as
  the LDAP container's own bootstrap secret). Rotating it is a natural
  follow-up, not done in this pass — out of scope for this feature and
  arguably belongs with the broader credential-rotation follow-up
  already flagged in ADR 0047.
- No self-service password reset, no email delivery, no username
  validation beyond what LDAP itself enforces (a duplicate `uid`) — all
  explicitly deferred, consistent with the smallest-safe-slice framing
  used for every phase in this project.
