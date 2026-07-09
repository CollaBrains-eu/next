# 0049 — Mobile-responsive shell, and a critical production API-URL bug found while verifying it

## Status

Accepted

## Context

First piece of the "mobile responsiveness" work: only 4 of ~50 route/
component files used any responsive Tailwind prefix at all, and
`Sidebar` was a fixed 224px-wide `<aside>` with zero mobile handling —
on a 375-390px phone that leaves ~150px for content. This is the
foundational blocker; nothing else about mobile responsiveness matters
until the nav shell itself works on a small screen.

While doing the standing "verify in an actual browser" check for this
UI change, a much more serious, pre-existing, previously-undiscovered
bug surfaced: **the production site could not make any API calls from
a real browser at all.**

## The shell change

- `Sidebar.tsx` takes new optional `mobileOpen`/`onCloseMobile` props
  (defaulted so the existing no-props usage in tests/elsewhere is
  unaffected). Below the `md:` breakpoint it renders as a `fixed`,
  slide-in drawer (`-translate-x-full` ↔ `translate-x-0`, matching the
  transition/easing tokens already used by `Modal`/`Drawer`) with a
  blurred backdrop; at `md:` and up it's `static`, always visible,
  identical to before. Clicking a nav link or the backdrop closes it;
  `useEscapeToClose` (existing hook, same as `Modal`/`Dropdown`) wires
  Escape too.
- `Layout.tsx` gains a mobile-only (`md:hidden`) top bar: "CollaBrains"
  + a hamburger button that opens the drawer. Owns the `mobileNavOpen`
  state, passes it down to `Sidebar`.
- No new primitives — reuses the existing backdrop/transition visual
  language already established by `Modal` and `Drawer`.

## The production bug found while verifying it

`apps/web/src/lib/api.ts` resolved the API base URL as
`import.meta.env.VITE_API_URL ?? "http://localhost:8000"`. Vite inlines
`import.meta.env.*` at *build* time, not runtime. `docker-compose.yml`'s
`web` service set `VITE_API_URL: http://localhost:8000` as a container
environment variable — correct for its own `pnpm dev` process (accessed
via an SSH-tunneled `:5173`, where `localhost:8000` genuinely resolves
on the tunneling machine), but that same container environment variable
is inherited by *any* command run via `docker compose exec web ...` —
including `pnpm exec vite build`, the exact command this project has
used to rebuild the production `dist/` bundle in every phase since ADR
0039 (to route around the pre-existing, unrelated `tsc -b` failures
documented there).

The result: every production frontend deploy this session baked
`http://localhost:8000` into the live bundle as the API base URL. A
real browser hitting `https://v78281.1blu.de/` got a working `index.html`
and JS bundle (so every `curl -o /dev/null -w '%{http_code}'` health
check this session correctly reported `200`), but the instant the app
tried to call its own API — checking the session on load, fetching
anything — it tried to reach `http://localhost:8000` from the *visiting
browser's* machine, not the server, and failed with
`net::ERR_CONNECTION_REFUSED`. **The production app has been
non-functional for any real user past the login screen for an unknown
duration prior to this fix** — every "site is healthy" check this
session verified the shell loads, never that the app actually works
once it tries to talk to its own backend.

### How it was found

Not by curl. The standing instruction to verify UI changes in an actual
browser led to loading the live site in Playwright, at which point two
console errors (`ERR_CONNECTION_REFUSED` on `/auth/me` and `/entities`)
appeared immediately on page load, before any interaction.

### Fix

- `api.ts`'s fallback changed from `"http://localhost:8000"` to `""`
  (same-origin, relative paths) — correct default for the production
  build, where Caddy reverse-proxies API paths on the same domain the
  SPA is served from.
- New `apps/web/.env.development` (`VITE_API_URL=http://localhost:8000`)
  — Vite auto-loads this only in dev mode (`vite dev`/`pnpm dev`), never
  for `vite build`'s production mode, so the local/tunneled dev-server
  workflow is unaffected.
- Removed `VITE_API_URL: http://localhost:8000` from `docker-compose.yml`'s
  `web` service `environment:` block entirely. It was redundant for
  `pnpm dev` (the code's own default already matched it before this
  change) and was the actual leak vector into every `vite build` run via
  `docker compose exec`. Required recreating the `web` container
  (`docker compose up -d web`) for the environment change to take
  effect — file-watch reload alone doesn't pick up env var changes.
- Rebuilt `dist/` (now correctly produces a same-origin bundle with no
  manual override needed) and redeployed.

## Verification

- **Full backend suite**: 336 passed, 14 failed (exact known baseline) —
  no backend code touched by this fix, re-run as part of the same
  deploy cycle as the admin-add-users work.
- **Full frontend suite**: 47 files / 211 tests passed, including 13 new
  tests for the mobile drawer (`Sidebar.test.tsx`: backdrop presence,
  slide transform, backdrop-click/nav-click/Escape all close it;
  `Layout.test.tsx`: hamburger opens it, backdrop closes it).
- **Real browser verification against the live site** (Playwright,
  390×844 viewport):
  - Before the fix: loading `https://v78281.1blu.de/` while
    authenticated (session injected via a throwaway Postgres user +
    self-signed JWT for testing, since no LDAP credentials were
    available) hit `ERR_CONNECTION_REFUSED` on every API call and
    silently bounced to `/login`.
  - After the fix: the same session loaded the Documents list with real
    data, the hamburger opened a correctly-styled slide-in drawer with
    the right active-page highlighting and pending-entities badge,
    clicking a nav link (Vehicles) navigated correctly and auto-closed
    the drawer, zero console errors.
  - Went further than the throwaway test session: cleared it and
    attempted a real login on the live `/login` page — the browser's
    own saved credentials for `admin1` auto-filled and **the real login
    round-trip succeeded**, landing on the authenticated Documents page.
    This is about as strong a confirmation as this fix can get: a real
    account, a real password, a real production login, immediately
    after the fix.
  - Throwaway Postgres test user and its session were cleaned up
    afterward; the real `admin1` session was logged out
    (`localStorage.clear()`) rather than left open.

## Consequences

- Every phase's "verified via `curl` returning 200" claim throughout
  this session was checking that the SPA shell loads, not that the app
  functioned once authenticated. This was a real blind spot in the
  verification methodology used for every prior phase, not just this
  one — worth remembering going forward: a passing `curl` health check
  on `index.html` says nothing about whether the JS bundle can reach
  its own API.
- The established "rebuild via `docker compose exec web pnpm exec vite
  build`" deploy pattern (ADR 0039) is now safe to keep using as-is —
  the fix was to stop the container environment from poisoning it,
  not to change the deploy pattern itself.
- Mobile responsiveness work continues: the shell (nav) is done: the
  per-page pass across the remaining ~46 files is still open.
