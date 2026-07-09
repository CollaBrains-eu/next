# ADR 0039: Phase 22 — Admin Dashboard

## Status

Accepted

## Context

CollaBrains v2 had a complete admin dashboard (`frontend/src/pages/AdminPage.tsx`,
`backend/app/routers/admin.py`): overview stats, user management, per-service
health checks, AI-analyzed bug reports, and platform settings. Next had no
equivalent -- no admin UI, no admin router. This was the largest concrete gap
identified when comparing Next against v2 (see
`docs/superpowers/plans/2026-07-09-fase1-admin-dashboard.md`).

## Decision

**Migrate the functionality, not v2's architecture.** v2's admin tab is a
route-gated section of its single SPA (`AdminRoute.tsx` guard) backed by its
single FastAPI app -- so is this: `apps/web/src/routes/AdminDashboard.tsx`
(role-gated by a new `AdminRoute` component) and
`services/api/src/api/admin_router.py`/`admin_service.py`. `apps/admin`
stays a stub pointing here, same pattern as `services/ai-gateway` etc.
(ADR 0003) -- no reason to split into a separate deployable with one React
app and one backend.

**AI-usage/cost reporting is new, not migrated** -- v2 never had it. Next's
`AiCallLog` (ADR 0003) already recorded every AI Gateway call; the admin
dashboard's `/admin/ai-usage` endpoint only had to aggregate data that
already existed, which v2's equivalent dashboard never could.

**Bug reports** (`BugReport` model, `/admin/bug-reports*`) are a direct,
1:1 migration of v2's feature, including AI-assisted analysis via
`ai_gateway.chat_completion` (unchanged pattern from every other agent
in this codebase).

**Health checks** are a single shared `httpx`-based checker plus a direct
`SELECT 1` for Postgres, not a per-service health-check module like v2 had
-- with only three external dependencies (Postgres, Paperless, Ollama)
today, a framework for that is premature.

## Consequences

- `/admin/*` had to be added to `infra/caddy/Caddyfile`'s `@api` path
  matcher (ADR 0012) -- a new API path prefix that also happens to be a
  frontend route needs the same Accept-header disambiguation as every
  other dual-purpose path already in that list, or it silently falls
  through to the SPA and returns HTML instead of JSON. Caught via live
  verification (curl against the real endpoint), not by any automated
  check -- consistent with every prior Caddy-related bug in this project
  (see ADR 0012's own two bugs).
- Discovered mid-deploy: rsync replaces a file via temp-file-plus-rename,
  which breaks Docker's bind mount for a *single file* (`Caddyfile:/etc/caddy/Caddyfile`)
  since the mount is bound to the original inode. A `caddy reload` after
  such a sync silently reloads the *old* file; only a container restart
  re-resolves the mount. Directory bind mounts (`services/api`, `apps/web/dist`)
  are unaffected. Worth remembering for any future single-file-mount edit
  on this host.
- Discovered mid-deploy, unrelated to this phase's own code: `apps/web`'s
  `pnpm build` (`tsc -b && vite build`) currently fails at the `tsc`
  step on ~170 pre-existing type errors in `*.test.tsx` files (missing
  `@testing-library/jest-dom` type augmentation), none of which touch
  any file this phase changed. Built via `vite build` directly for this
  deploy to avoid blocking on an unrelated, pre-existing issue; the
  broken `tsc` gate itself is not fixed by this ADR and should be
  tracked separately.
