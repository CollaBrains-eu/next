# 0067 — Priority 1 security/quality hardening: what shipped

## Status

Accepted

## Context

ADR 0066 (the enterprise-SaaS audit) produced a P1-P4 roadmap and was
explicitly approved to execute P1 as small, independently reviewable
commits without waiting for per-commit sign-off. This ADR records what
actually shipped from that list, same convention as ADR 0065.

## Decision

All six P1 items shipped as seven commits (`d8dffbf`..`584b0ae`):

1. **WCAG contrast** (`d8dffbf`) — `apps/web/src/styles/tokens.css`'s
   `--text-3`/`--accent`/`--success`/`--danger` were still the exact
   values ADR 0063 had already computed as failing 4.5:1 in the design
   artifact; that fix landed in the artifact but never in the real
   app's tokens. Ported the artifact's already-verified values across,
   darkened `--accent-hover` to stay distinct now that `--accent` moved
   to the old hover shade, bumped dark-mode `--text-3` opacity 0.38→0.60.
   Added a luminance/contrast-ratio regression test
   (`designTokens.test.js`) computed from the real token values, so
   this can't silently regress between a reference doc and the shipped
   app again. Verified live in a real browser (light + dark) via
   Playwright against the local dev server, and against real network
   traffic to confirm no other token consumers broke.
2. **CSP/HSTS/security headers + CORS** (`ad996d1`, `8844eef`) —
   `infra/caddy/Caddyfile` had zero security headers; added CSP (source
   list verified against real network traffic: Google Fonts + the one
   external fetch in `Landing.tsx`'s IP-geolocation call), HSTS,
   `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
   `Permissions-Policy`. Bundled the roadmap's paired CORS fix:
   `allow_origins` was hardcoded to the dev origin with credentials
   enabled; now a `CORS_ALLOWED_ORIGINS` env setting, with a regression
   test asserting an unconfigured `Origin` gets no
   `access-control-allow-origin` back.
3. **OpenLDAP ACLs** (`d86d8d1`) — `slapd.conf.template` had no `access
   to` directives at all (default-allow read, `userPassword` included,
   for any bind reachable on the Docker network). Added ACLs;
   `rootdn` still bypasses them entirely (standard OpenLDAP behavior),
   so the app's admin-bind paths are unaffected, and grepping
   `ldap_auth.py` confirmed the app never opens an anonymous connection,
   so restricting anonymous reads removes no capability the app uses.
4. **Backup encryption** (`6348f8c`) — `infra/backup/backup.sh`'s three
   dumps (Postgres, LDAP, Signal keys) landed as plaintext with no
   offsite copy. Each now streams through `gpg --symmetric --cipher-algo
   AES256` so plaintext never touches disk; a new required
   `BACKUP_ENCRYPTION_PASSPHRASE` env var, script refuses to run without
   it. Restore runbook updated with the matching decrypt step
   everywhere. Offsite replication is explicitly out of scope here (a
   separate destination/credentials decision).
5. **Dead lint script** (`db311a3`) — `apps/web`'s `pnpm lint` failed
   outright, `eslint` was never installed. Added a flat
   `eslint.config.js` (typescript-eslint + `eslint-plugin-react-hooks`
   pinned to the classic 5.2.0 line, not 6.x/7.x's React-Compiler
   ruleset + `eslint-plugin-react-refresh`). Running it surfaced only
   11 issues across ~150 files — fixed all of them (6 legitimate
   Provider+hook co-location patterns allowlisted by name, 5
   `exhaustive-deps` warnings on intentional mount-only effects handled
   the same way this codebase already handles that case elsewhere).
   `pnpm lint` and the full 543-test vitest suite both green.
6. **Non-root containers** (`584b0ae`) — `services/api` and
   `apps/signal-bot` ran as root for no reason; both confirmed to need
   no filesystem writes under `/app` at runtime. `apps/web` is
   deliberately **not** touched — its `node_modules` anonymous volume
   already exists root-owned on the live host from years of history,
   and switching users there without a one-time manual re-chown would
   break the established `docker compose exec web pnpm install`
   workflow. `infra/ldap`'s Dockerfile also isn't touched — its
   entrypoint already drops `slapd` itself to the unprivileged
   `openldap` user, same goal via a different mechanism.

## Verification

Every commit ran its narrowest relevant test surface before landing:
`vitest run` (543/543 passing throughout), the new WCAG contrast tests,
the new CORS tests (`test_health.py`), a live Playwright check of the
contrast fix in both themes, and a real-network-trace check of the CSP
source list. Two categories had no automated test available in this
environment and are called out explicitly in their commits rather than
silently assumed correct:

- **Caddyfile and `slapd.conf.template` syntax**: no Docker/Caddy/slapd
  available locally to validate against a live instance. Both were
  checked by hand against each tool's documented syntax; both need a
  real `caddy validate` / real `slapd` startup (not `slaptest` — see
  prior project history on why) at actual deploy time.
- **`backup.sh`'s gpg invocation and both Dockerfiles**: no gpg or
  Docker available locally either. `backup.sh` passed `bash -n`;
  installing gpg locally to go further pulled in a from-source Python
  3.14 + meson + gnutls build chain and was abandoned as disproportionate
  to what it was verifying. The Dockerfile changes were checked by
  reasoning through actual runtime filesystem writes (none found under
  `/app` for either service) rather than a build+run smoke test.

None of this blocks shipping the commits — each is small, reviewable,
and reversible on its own — but all four should get one real
verification pass (an actual deploy, or a Docker-capable environment)
before being trusted as fully proven rather than carefully reasoned.

## Consequences

P1 is complete. Remaining open items from ADR 0066, carried forward
unchanged:

- `apps/web`'s Dockerfile non-root conversion (needs a live-host
  re-chown step, not a code-only fix).
- The deploy-time verification gaps listed above (Caddy, LDAP ACLs,
  backup encryption, both Dockerfiles) should be confirmed for real on
  the next actual deploy, not just trusted from this pass.
- P2 (Sentry, CI pipeline, Playwright smoke suite, missing FK indexes,
  overlay ARIA/focus-trap parity, `Workspace.tsx`/`Vehicles.tsx`
  responsive+i18n fixes) is next, per ADR 0066, pending go-ahead.
