# 0053 — Critical: JWT_SECRET was the public `.env.example` placeholder in production

## Status

Accepted

## Context

While following up on the deferred "rotate other credentials" item from
ADR 0047 (root password) and ADR 0048 (LDAP admin password), checked
every secret in production `.env` against `.env.example`. All four were
identical:

```
JWT_SECRET=changeme-generate-a-real-secret
POSTGRES_PASSWORD=changeme
PAPERLESS_ADMIN_PASSWORD=changeme
LDAP_ADMIN_PASSWORD=changeme
```

**`JWT_SECRET` being unrotated is a critical, actively-exploitable
vulnerability, independent of and more severe than the cryptomining
compromise (ADR 0047).** `CollaBrains-eu/next` is a **public** GitHub
repository (confirmed via `gh api repos/CollaBrains-eu/next --jq
.visibility` → `"public"`). `.env.example` is tracked in it. Anyone —
with zero prior access to this server, this repo's issue tracker, or
anything else — could read that file on GitHub, see the exact string
`changeme-generate-a-real-secret`, and forge a valid `HS256` JWT for
any username with `role: "admin"`, signed with that known secret. Every
admin endpoint (including the LDAP-write `POST /admin/users` from ADR
0048) would accept it. This requires no SSH access, no LDAP credential,
no exploit beyond reading a public file and making one HTTP request —
strictly worse than the SSH brute-force vector in ADR 0047, which at
least required guessing or otherwise obtaining a real password.

This was **not found by the compromise investigation** (ADR 0047,
0052) — it's unrelated to the cryptominer, was never exploited as far
as any log reviewed shows, and would have been a live hole regardless
of whether the SSH compromise had ever happened.

## What was rotated, and how

Each of these four systems stores/derives its credential differently at
runtime, discovered while doing this (documented so a future rotation
doesn't have to rediscover it):

- **`JWT_SECRET`** — pure application config, read fresh by FastAPI on
  each request via `settings.jwt_secret`. Generated a new 32-byte hex
  secret (`openssl rand -hex 32`), updated `.env`, recreated the `api`
  container (`docker compose up -d api`). This alone invalidates every
  existing session immediately — every logged-in user, including
  admins, is signed out and must re-authenticate. That's the point, not
  a side effect to work around.
- **`POSTGRES_PASSWORD` / `DATABASE_URL`** — Postgres's actual
  credential lives in its own auth catalog, set once at first
  container init; changing the env var alone does nothing for an
  already-initialized database. Ran `ALTER USER collabrains WITH
  PASSWORD '...'` directly against the live database, then updated
  both `POSTGRES_PASSWORD` and the embedded password in `DATABASE_URL`
  in `.env`, then recreated `api` (compose also recreated `postgres`
  itself, since its own environment block references the same var —
  safe, reuses the existing data volume, no data loss).
- **`LDAP_ADMIN_PASSWORD`** — this project's LDAP container
  (`infra/ldap/`) is custom-built around classic `slapd.conf`, not
  `cn=config`. `entrypoint.sh` runs `slappasswd -s "$LDAP_ADMIN_PASSWORD"`
  and regenerates `rootpw` in `slapd.conf` from the environment
  variable on **every** container start, not just first boot — unlike
  the more common osixia/openldap image pattern, where the root
  password is fixed at first init and needs an in-directory
  `ldappasswd`/`ldapmodify` to change later. The correct rotation here
  is simply: update `.env`, `docker compose up -d openldap`. (A first
  attempt to use `ldappasswd` against `cn=admin,...` correctly failed
  with "No such object" — that DN isn't a real directory entry in this
  setup, it's the config-file `rootdn`.)
- **`PAPERLESS_ADMIN_PASSWORD`** — Paperless-ngx is Django underneath;
  its admin user's password is a normal Django auth record, unrelated
  to `PAPERLESS_ADMIN_PASSWORD` after Paperless's own first boot.
  Rotated via `manage.py shell` (`User.objects.get(username="admin");
  u.set_password(...); u.save()`), then updated `.env`. `api`'s
  `paperless_client.py` uses this credential on every document
  upload/OCR call, so `api` needed recreating again to pick it up —
  verified with a real authenticated request against Paperless's API
  (`200`, not just "container started").

Also rotated the **root SSH/console password** (flagged as burned in
ADR 0047, deferred at the time) — generated and set via `chpasswd`.
With `PasswordAuthentication no` already in place, this isn't an SSH
attack surface, but the old value was known-compromised and had no
reason to remain valid for console/recovery access.

## An error made and caught during this work

The first `LDAP_ADMIN_PASSWORD` rotation attempt generated the new
password in one shell command and tried to use it in a **separate**
subsequent command — shell variables don't persist across separate
tool invocations in this environment. The `sed` substitution silently
wrote an **empty** password to `.env`, and `docker compose up -d
openldap` immediately crash-looped
(`entrypoint.sh: LDAP_ADMIN_PASSWORD: LDAP_ADMIN_PASSWORD is required`)
— a real, if brief, LDAP/login outage. Caught immediately via
`docker compose logs`, fixed by generating and applying the password
within a single atomic command, verified working before moving on. All
other rotations in this ADR were done atomically from the start once
this was caught.

## Verification

- **JWT_SECRET**: forged a JWT using the exact old public placeholder
  string as the signing key (`sub: admin1, role: admin`), sent it to
  `GET /admin/stats` — before rotation this would have granted full
  admin access; after, it correctly returned `401 Could not validate
  credentials`. This is the load-bearing proof for this ADR, not the
  container-restarted-cleanly check.
- **Postgres**: `api` started and served `200` against the new
  `DATABASE_URL` (would fail immediately on a bad password).
- **LDAP admin**: `ldapwhoami` with the old password → `Invalid
  credentials (49)`; with the new password → succeeds. The
  admin-create-user feature from ADR 0048 exercised end-to-end with the
  new password (created a real throwaway user, confirmed via
  `ldapsearch`, deleted it).
- **Paperless**: a real authenticated GET against Paperless's own
  `/api/documents/` using `settings.paperless_admin_password` (i.e.
  exactly how `paperless_client.py` uses it in production) returned
  `200`.
- Full stack health re-checked after all four rotations: site `200`,
  Signal `204`, Ollama `200`, all ten containers `Up`/healthy, no new
  errors in `api` logs.

## Consequences

- Every user session was invalidated by the JWT_SECRET rotation —
  everyone, including admins, needs to log in again. Expected and
  necessary, not a bug.
- The new root password is a generated value known only to whoever
  receives it directly (not committed anywhere) — SSH access is
  unaffected since password auth is already disabled; this only
  matters for console/recovery access.
- `.env.example`'s placeholder values remain `changeme*` on purpose —
  that file's job is to show the shape of the config, not hold real
  secrets. The bug was never that file; it was production never having
  replaced its copy.
