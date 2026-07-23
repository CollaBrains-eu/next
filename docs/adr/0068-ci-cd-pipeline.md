# 0068 — CI/CD pipeline

## Status

Accepted

## Context

ADR 0066 (Priority 2, item 1) called for a real CI/CD pipeline: this repo
had none (`deploy_collabrains.sh` deployed straight to the only production
host with zero automated test/lint gate beforehand). Designed from what the
test suite and Dockerfiles actually need, not a generic template.

**Real bug found while wiring `uv sync` into CI, unrelated to CI itself but
blocking it**: `services/api/uv.lock` (committed 2026-07-19, "for
reproducible installs") was stale from the moment it landed. Root
`pyproject.toml` declares a `[tool.uv.workspace]` with `services/api` as
the only member, which means `uv` resolves and writes the lockfile at the
**workspace root**, not inside the member directory — confirmed directly:
`uv lock` run from `services/api` reported "Existing uv.lock satisfies
workspace requirements" and touched a root-level `uv.lock` that was never
tracked by git at all (`git log --all -- uv.lock` returns nothing). So the
tracked file had been silently providing zero reproducibility since the
day it was committed; adding `ruff` to `dependency-groups.dev` for this
same PR was what actually surfaced it (the stale file simply didn't
change). Fixed by deleting the stale `services/api/uv.lock` and committing
the real workspace-root `uv.lock` instead — `uv sync --group dev` run from
`services/api` (exactly what CI does) correctly resolves through it
regardless of invocation directory, confirmed by testing both.

**What the backend test suite actually requires** (checked by reading it,
not assumed): every test that touches LDAP or the AI Gateway mocks those
calls (`patch("api.auth.ldap_authenticate", ...)`,
`patch("api.admin_router.ldap_set_password", ...)`,
`patch("api.admin_service.chat_completion", ...)`, etc.) — grepping for
every test file that calls `ldap_auth.create_user`/`set_password`/
`delete_user` directly (i.e. without mocking) returned zero results. The
suite needs a **real Postgres** (asserted directly against live DB state)
and a **real Redis** (rate limiting, WebAuthn challenge storage — no mock
found), but genuinely never opens a live LDAP connection or calls a live
Ollama. This means CI doesn't need to build+boot the custom `openldap`
image (or run Ollama at all) just to run `pytest` — a real finding that
significantly simplified the backend job versus assuming the full
docker-compose stack was required.

**Frontend build validation uses `vite build`, not `tsc -b`**, matching how
this repo already builds for real (`docker-compose.yml` comment cites ADR
0039/0049: `tsc -b` is routed around because of a pre-existing
`react-router-dom`/`@types/react` version-mismatch type error unrelated to
any one change — confirmed still present by running `tsc -b` directly, e.g.
`'Link' cannot be used as a JSX component` from a React 18/19 type overlap).
Re-litigating that mismatch is out of scope for a CI-pipeline PR; it's
tracked as a Priority 3 item (ADR 0066) instead of silently adding a gate
this repo doesn't otherwise enforce.

**Local environment note surfaced while verifying this** (not a CI
finding, a dev-machine one): this session's local Postgres was 6 migrations
behind head and Redis wasn't running at all, which made the full backend
suite look like it had 301 failures. Neither was a real regression —
`alembic upgrade head` and starting `redis-server` brought it back to a
clean baseline. Worth remembering: a large sudden failure count in this
suite is worth checking against "is my local environment actually current"
before assuming a real break.

## Decision

`.github/workflows/ci.yml`, four independent jobs, all running on every
push to `main` and every PR:

1. **frontend** — `pnpm install --frozen-lockfile` → `pnpm --filter web
   lint` (the eslint config from ADR 0067) → `pnpm --filter web test`
   (vitest) → `pnpm --filter web exec vite build`. pnpm store cached via
   `actions/setup-node`'s built-in `cache: pnpm`.
2. **backend** — Postgres (`pgvector/pgvector:pg16`, matching
   `docker-compose.yml` exactly) and Redis (`redis:7-alpine`) as GitHub
   Actions service containers (no custom-build needed, both are
   registry-pullable, unlike `openldap`). `uv sync --group dev` → `ruff
   check` → a migration-heads check (fails if `alembic heads` ever reports
   more than one head, i.e. an unmerged migration branch) → `alembic
   upgrade head` → `pytest`. uv's own dependency cache handles caching.
3. **security** — `pnpm audit --audit-level=high` and `pip-audit`, both
   **report-only** (`|| true`), not blocking. Both currently surface
   pre-existing findings unrelated to this pipeline: a transitive
   `brace-expansion` DoS advisory (100+ paths, all under
   `apps/mobile`'s Expo/React Native dev-tooling chain — not this app's
   runtime, and not something to fix by unilaterally bumping mobile deps
   mid-unrelated-feature-work) and an `ecdsa` advisory
   (`PYSEC-2026-1325`) with no listed fix version yet. Hard-failing CI on
   day one for two pre-existing, currently-unfixable findings would just
   train everyone to ignore the security job; report-only now, tighten to
   fail-on-high once each is individually resolved (a Priority 3/4 item,
   not this one).
4. **docker-build** — matrix build (no push) of all four real Dockerfiles
   (`api`, `web`, `signal-bot`, `openldap`) using
   `docker/build-push-action` with GitHub Actions cache, catching a broken
   Dockerfile before it ever reaches a deploy.

**No GitHub Secrets are required for this workflow** — every credential in
the backend job is a throwaway value scoped to that run's own ephemeral
service containers (`collabrains-ci-test`, etc.), never a real secret, and
nothing here pushes an image or deploys anywhere. If a future workflow adds
a real deploy step or Sentry release/source-map upload (ADR 0066 Priority
2, item 4), that step will need real secrets (e.g. `SENTRY_AUTH_TOKEN`) —
document those in this ADR's Consequences section when that lands, not
before.

## Consequences

- Every PR now gets: a real lint/test/build gate on both frontend and
  backend, a migration-branching guard, a Docker-build smoke test, and
  visible (non-blocking) security-scan output — all zero before this ADR.
- `tsc -b` is still not part of any gate. This is a known, tracked gap
  (Priority 3), not an oversight — see Context above for why.
- The security job needs revisiting once the two flagged advisories are
  individually resolved, to make it fail-on-high like a normal gate instead
  of report-only.
- This workflow validates the repo in isolation; it does not deploy
  anything, matching the explicit instruction not to automate production
  deploys yet.
