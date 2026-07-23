# 0069 — Playwright smoke suite

## Status

Accepted

## Context

ADR 0066 (Priority 2, item 2) called for this project's first automated E2E
suite — confirmed by the audit as genuinely absent (no `playwright.config.*`
anywhere, only years of manual browser verification recorded in ADRs). Goal
per the brief: "can we detect if production is broken before release?" —
reliability over coverage.

**New workspace package** `apps/e2e` (fits the existing `apps/*` pnpm
workspace glob) rather than nesting under `apps/web`, since these tests
exercise the whole running app (frontend + real API + real Postgres/Redis/
LDAP) as a black box, not `apps/web`'s source in isolation the way vitest
does.

**Scope decisions, each deliberate:**

- **Real login, not mocked.** `loginViaApi` in `tests/fixtures.ts` gets a
  real JWT from the real `/auth/token` endpoint and seeds `localStorage`
  directly — faster than re-driving the login form for every test, but
  still a real credential check against real LDAP, not a stub. Exactly one
  test (`login.spec.ts`) drives the actual form, since the login UI itself
  is also something to catch a regression in.
- **AI chat: availability, not a real generation round trip.** This
  project's chat model is CPU-bound and can take well over a minute per
  reply on production (`docs/deployment/ai-optimization.md`), and no
  Ollama runs in the CI job this suite runs in (see below). `chat.spec.ts`
  checks the page loads and the input is present/enabled — that's what
  "AI chat availability" means for a *smoke* suite. A real generation test
  needs its own slower, separately-scheduled suite if one gets built later,
  not a blocking gate on every PR.
- **No Caddy in the CI path.** Production topology is
  browser → Caddy (TLS, Accept-header routing) → `api`. Reproducing that
  in CI would mean a second, CI-only Caddyfile (`collabrains.eu {...}`
  expects a real domain + Let's Encrypt) just to test routing rules that
  were already validated live via `caddy validate` + a real reload during
  the Priority 1 deploy (ADR 0067) and rarely change. Instead: the frontend
  is built with an absolute `VITE_API_URL` pointing straight at the `api`
  container's port. This tests the thing most likely to actually regress
  (frontend/backend contract, real auth, real rendering) without
  maintaining a parallel routing config purely for tests.
- **No Ollama, no Paperless, no Signal, no Caddy containers in CI at
  all** — confirmed by reading `docker-compose.yml`'s `depends_on` that
  `api` doesn't require any of them to start, and none of this suite's
  journeys need OCR, real AI generation, or Signal. Keeps the CI job fast
  and avoids downloading multi-gigabyte models on a shared runner.
- **Chromium-based mobile profile (`devices["Pixel 7"]`), not an iOS/WebKit
  one**, for the responsive-layout checks. This suite is checking CSS
  breakpoints, not engine-specific rendering — and Playwright's bundled
  WebKit build isn't installable on every dev machine (confirmed: fails
  outright on macOS 13). Chromium keeps the suite runnable everywhere
  without losing what the check is actually for.
- **`responsive.spec.ts` only covers Landing/Login/Dashboard for now.**
  The Priority 1 audit found `Workspace.tsx` (`/documents`) and
  `Vehicles.tsx` have zero responsive breakpoint classes today — adding an
  assertion against them here, ahead of actually fixing that (Priority 2,
  item 5), would just commit a known-red test. Extend this file once that
  fix lands.
- **Disposable LDAP test users**
  (`e2e-user`/`e2e-admin`), created via `ldap_auth.create_user` the same
  way every prior live-verification pass in this project has (ADR
  0065/0067) — real accounts against the real auth path, provisioned fresh
  by CI (ephemeral LDAP container, torn down with the job) and never
  cleaned up individually since the whole container disappears anyway.

**Local verification performed**: every test that doesn't need a real
backend (landing page, protected-route redirect, both responsive checks
that don't require `authedPage`) was run for real against a local Vite dev
server and passed. The auth-dependent tests (`dashboard`, full login,
`chat`, `documents`, `admin`, `settings`, the mobile dashboard check)
couldn't be verified locally — this dev machine has no Docker, so no way to
build/run the custom OpenLDAP image — and get their first real run in CI
itself.

## Decision

`apps/e2e/`: `playwright.config.ts` (two projects, `desktop` for
everything except `responsive.spec.ts`, `mobile` for that file only),
`tests/fixtures.ts` (credentials + `loginViaUi`/`loginViaApi` helpers +
`authedPage`/`adminPage` fixtures), and 8 spec files covering every journey
from the Priority 2 brief: landing, login/auth flow, dashboard, AI chat
availability, document listing, admin access (both directions — admin in,
non-admin redirected), settings/profile, and responsive layout.

`.github/workflows/ci.yml` gained an `e2e` job: builds+starts the real
`openldap` image, installs backend deps and starts `uvicorn` directly on
the runner (not via Docker — same reasoning as the `backend` job, and
`docker-build` already separately validates the Dockerfile builds),
creates the two disposable users, builds the frontend against that live
API, serves it via `vite preview`, then runs the suite. Uploads the
Playwright HTML report as a build artifact on any outcome (not just
failure) for easier debugging.

## Consequences

- Every PR now gets a real, running-app smoke check across the journeys
  that matter most for "is this broken," not just unit tests in isolation.
- `Workspace.tsx`/`Vehicles.tsx` responsive coverage is a follow-up, tied
  to the Priority 2 item 5 fix for those same files.
- A real-generation AI test, if ever wanted, needs its own suite and
  probably its own schedule (not on every PR) given the model's latency on
  this host — out of scope here, not forgotten.
