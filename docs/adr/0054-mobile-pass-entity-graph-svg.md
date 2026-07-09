# 0054 — Mobile pass round 2: EntityGraph's fixed-width SVG

## Status

Accepted

## Context

Continuation of the mobile-responsive pass (ADR 0049, 0050). Surveyed
the remaining unaudited route files in a real 390×844 browser session
(Settings, Vehicles, Login, Assistant, Workspace — which is the `/`
route, already covered as "Documents" in ADR 0050 — EntityReview,
EntityGraph, Legal, NotFound), completing all 16 files under
`apps/web/src/routes/`.

## What was already fine (no changes)

Settings, Vehicles, Login (the sign-in form itself), Assistant,
EntityReview, Legal, NotFound all rendered correctly at mobile width
with no changes needed.

**Noted but explicitly out of scope**: the mobile hamburger on `/login`
opens the full authenticated nav sidebar even though no one is logged
in (no user-info footer shows, since that's correctly gated on
`user &&`, but the nav links themselves are visible and clickable).
This is pre-existing behavior, not something the mobile work
introduced or regressed — `App.tsx` wraps every route including
`/login` in `<Layout>`, outside `<ProtectedRoute>`, so `Sidebar` has
always rendered regardless of auth state; this is presumably visible
on desktop today too as a static sidebar next to the login form. Not
touched here — it's an auth/routing architecture question, not a
responsive-design bug, and changing it wasn't asked for.

## What was broken, and the fix

**`EntityGraph.tsx`**: the one-hop relationship graph's `<svg>` had a
hardcoded pixel `width={700}` (and `height={480}`) with no responsive
handling at all — on a 390px viewport the graph rendered at its full
700px width, pushing the actual content (nodes, edges, labels) almost
entirely outside the visible area; what showed was mostly the graph's
empty left margin, with node circles and labels clipped at the right
edge.

Fixed with the standard responsive-SVG pattern: `width="100%"` (drop
the fixed pixel `width`/`height` attributes), keep `viewBox="0 0 700
480"` so the internal coordinate system used by all the position math
(`CENTER`, `RADIUS`, node placement) is unchanged, and cap growth on
wide screens with `style={{ maxWidth: WIDTH }}` — this reproduces the
original fixed-700px desktop appearance exactly on anything ≥700px
wide, while scaling proportionally down (SVG's default
`preserveAspectRatio="xMidYMid meet"` handles this automatically) on
anything narrower. Removed the now-unnecessary `overflow-x-auto` on
the wrapper `<div>` — the SVG no longer overflows, it shrinks to fit.

## A false alarm caught during verification, worth recording

The first post-deploy mobile screenshot showed the *exact same* broken
layout as before the fix — looked like the fix hadn't taken effect.
Confirmed the deployed source file on the server did have the change,
and a fresh `vite build` had produced a new JS bundle hash
(`index-CHrPl-GY.js`). The browser tab was still running the *previous*
bundle (`index-UZ_NL_vz.js`) — a stale cached `index.html` from an
earlier navigation in the same Playwright session, not a real
deployment failure. A hard reload (`location.reload(true)`) picked up
the new bundle immediately and the fix was confirmed working correctly.

Checked whether this points to a real production caching problem (a
real user's browser serving a stale SPA shell after a deploy) —
inconclusive, and not fixed speculatively. Caddy's config
(`infra/caddy/Caddyfile`) uses plain `file_server` with no explicit
`Cache-Control` override, which defaults to ETag-based conditional
requests rather than a long blind `max-age`, and the JS/CSS bundles are
already content-hashed per build (only `index.html` itself could ever
go stale). This looks more like a same-session Playwright navigation
cache quirk than a real Caddy misconfiguration, but it's not proven
either way — noted here rather than "fixed" without evidence, per the
project's general practice.

## Verification

- Full frontend suite (live `web` container): 48 files / 217 tests
  passed — `EntityGraph.test.tsx` has no assertions on the SVG's
  width/height attributes, so no test changes were needed.
- Real browser re-verification (390×844, after a confirmed hard
  reload to rule out the caching false-alarm above): the graph now
  renders centered and fully contained within its card — both nodes,
  the edge, and all labels visible, matching the desktop layout
  proportionally scaled down.
- Production bundle rebuilt; site returns `200`.

## Consequences

All 16 route files have now been surveyed at least once for mobile
overflow issues (ADR 0050 covered Entities, AdminDashboard,
DocumentDetail, CaseDetail; this ADR covers the rest). This closes the
*survey* pass — it does not mean every page has been polished for
mobile, only that no further blocking overflow/unusable-layout bugs
were found beyond what's already fixed. A more thorough pass (spacing,
touch-target sizing, information density on data-heavy pages) remains
open if wanted, distinct from "does it visibly break."
