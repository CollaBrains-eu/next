# Design system extension + Sidebar/Layout redesign — Design

## Status

Approved (brainstormed 2026-07-22)

## Context

User asked for a premium SaaS redesign of the whole authenticated app shell
(sidebar, dashboard, document experience, AI chat, login) plus a separate
cinematic landing page + onboarding flow, styled after Notion/Linear/Dropbox
and, for the landing/onboarding track, Apple Vision Pro/Linear
launch-page/Arc Browser. That request spans 7+ largely independent
subsystems — too large for one spec, consistent with how every prior
multi-capability phase in this project has been split (ADR 0009, 0053,
etc.). Decomposed with the user into:

1. **Design system + sidebar/layout** (this spec)
2. Dashboard redesign
3. Document experience redesign
4. AI Chat experience redesign
5. Login redesign
6. Landing page + onboarding flow (separate track, not started, has its own
   open architecture question — see below)

This spec covers only #1, the foundation the other authenticated-app pieces
will inherit from.

Audited the actual repo (`~/dev/collabrains-next`, in sync with
`origin/main` at `7cdba82`) rather than assuming a blank slate:

- `apps/web/src/styles/tokens.css` already has a real light/dark CSS-variable
  design system (accent `#6C63FF`, semantic surface/text/border tokens,
  per-theme-tuned shadows) — this is **not** a from-scratch design system
  build, it's an extension of Violet DS (see `docs/design/violet-design-language.html`,
  ADR 0063).
- `apps/web/tailwind.config.js` has motion tokens already (spring easing,
  `floaty`, `shimmer`, `cardIn`) but no gradient tokens and no
  glass/blur utility.
- `apps/web/src/components/Sidebar.tsx` is already more capable than a bare
  nav list: animated active-item pill (position/height computed from the
  active `NavLink`'s DOM rect), a mobile slide-in drawer with backdrop, a
  dark-mode toggle, a command-palette trigger, and an alerts bell. It is
  **not** collapsible (fixed `w-56`) and nav items have no icons.
- No logo or brand-mark asset exists anywhere in the repo (no `public/`
  directory, no favicon, no SVG mark) — the sidebar today shows only the
  text "CollaBrains".
- `apps/web/src/lib/navigation.ts` is a flat `{ to, labelKey }[]` array with
  no icon field; `navItemsForRole` appends `/admin` for admin users.

## Goals

1. Extend Violet DS with the tokens this redesign (and the later
   dashboard/documents/chat/login specs) will need: a brand gradient, a
   reusable glass-surface utility, and a named radius scale — additive
   only, no change to existing color/shadow/motion tokens.
2. Give CollaBrains a brand mark (small inline SVG, no external asset
   dependency) usable in the sidebar now and reusable later in
   Login/Landing.
3. Make the sidebar collapsible (expanded ↔ icon-rail), with the collapsed
   state persisted like the existing dark-mode preference.
4. Give every nav item an icon, visible in both expanded and collapsed
   states.
5. Do all of this without regressing anything the sidebar already does
   well (active pill, mobile drawer, dark mode, command palette, alerts).

## Non-goals

- Dashboard, document-experience, AI-chat, and login redesigns — separate
  specs, sequenced after this one.
- The landing page and onboarding flow — separate track. Note for
  whoever picks that up: the existing `Onboard.tsx` is an invite-token
  verification page (admin creates a user via LDAP with a temp password;
  this page confirms the token and links to `/login`), **not** a
  self-service "Personal / Team / Organization" account-type chooser —
  this app has no self-serve signup at all. The cinematic onboarding
  wizard described in the original brief has no existing flow to slot
  into and needs its own architecture decision before design work starts.
- New color hues. The brief asks for "subtle gradients where fitting" —
  staying within the existing violet accent family (violet→a cooler
  secondary like blue/indigo) rather than introducing new saturated
  colors, per the brief's own "rustig maar krachtig" (calm but powerful)
  and "niet overdreven" (not overdone) direction.
- Icon-rail collapse on mobile — the mobile experience is already a
  full-overlay drawer (`mobileOpen` prop + backdrop); an icon-rail concept
  doesn't apply there. Collapse is desktop (`md:` and up) only.
- Re-theming existing components that already consume the current tokens
  correctly (Card, Button, Tooltip, etc.) — only additive tokens, not a
  token migration.

## Design tokens (`tokens.css` + `tailwind.config.js`)

Additive changes only:

- `--gradient-brand`: a two-stop gradient (violet accent → a cooler
  secondary hue), defined once per theme (`:root` and `.dark`) so it
  automatically adapts. Used sparingly: the brand mark's fill, the active
  nav pill's leading edge, and (in later specs) premium CTAs — not a
  background wash anywhere.
- `.glass-surface` utility class: `backdrop-filter: blur(...)` +
  translucent `--bg-card`, consolidating the ad hoc blur/translucency
  already hand-rolled in a couple of dropdown components (e.g. the
  language switcher on the landing page) into one reusable rule.
- Named radius scale (`--radius-sm/md/lg/xl`) mapped to the values already
  in use (`rounded-lg/xl/2xl` today), documented so future components pick
  a token instead of guessing a Tailwind radius utility ad hoc. Existing
  components keep their current visual radius — this just names what's
  already there plus gives the new sidebar chrome something explicit to
  reference.

## Brand mark

**Superseded mid-implementation**: this section originally specified an
abstract inline-SVG placeholder mark, since no logo asset existed at
brainstorming time. The user supplied a real logo (the "collabrAIns"
mascot + wordmark lockup, PNG, flat white background, no alpha) partway
through Task 6's implementation. `apps/web/src/components/BrandMark.tsx`
now renders that real asset (`src/assets/brand/collabrains-logo.png`,
downscaled from the original to 500×250px) as a CSS `background-image`
inside a fixed-size white rounded badge, oversized and positioned so only
the mascot region shows — chosen over a literal file-crop because there's
no alpha channel to preserve and no image-editing tool in this environment
beyond `sips`' basic centered crop, and because any imprecision in the
oversized/repositioned background blends into the badge's own white
background seamlessly (the source's background is also flat white). The
wordmark span in the sidebar keeps its original plain-text treatment but
now highlights "AI" with `--gradient-brand` (`Collabr`+gradient `AI`+`ns`)
to match the real logo's own styling, cheaply, without needing a pixel-exact
text crop from the source image. Placed to the left of the wordmark in the
sidebar's expanded state; shown alone (wordmark hidden) in collapsed/icon-
rail state — this part of the original design is unchanged.

## Sidebar / Layout

**Collapse mechanic**: new `useSidebarCollapsed()` hook (same shape as the
existing `useDarkMode()` hook — reads/writes
`localStorage["collabrains_sidebar_collapsed"]`, defaults to expanded). A
toggle button (chevron icon) sits in the sidebar's top row next to the
brand mark, visible only at `md:` and up (mobile always uses the existing
full-drawer pattern, no collapse button shown there).

- **Expanded** (`w-56`, current width): brand mark + wordmark, icon + label
  per nav item, unchanged active-pill/tooltip behavior.
- **Collapsed** (`w-16`): brand mark only (wordmark hidden), icon-only nav
  items, existing `Tooltip` component wraps each item to show its label on
  hover (the component is already imported in `Sidebar.tsx` for the search
  button — reused, not new).
- Width transition uses the existing `duration-base ease-spring` timing
  token already applied to the mobile drawer's transform, so expand/collapse
  feels consistent with the drawer's existing motion language rather than
  introducing a new easing curve.
- The active-pill positioning logic (`pillStyle` state, computed from
  `itemRefs`) is unaffected by collapse — it already recomputes from live
  DOM measurements on `location.pathname` changes, and will naturally
  recompute correctly at the new collapsed width since the effect re-runs
  on nav-item layout regardless of which width triggered it. Verify this
  live rather than assuming (see Testing).

**Icons**: `navigation.ts`'s `NAV_ITEMS` gains an `icon` field (a
`lucide-react` component reference, already an installed dependency — no
new package). Mapping: Dashboard→`LayoutDashboard`, Documenten→`FileText`,
AI Chat→`Sparkles`, Legal draft→`Scale`, Taken→`CheckSquare`,
Kalender→`Calendar`, Entiteiten→`Users`, Dossiers/Cases→`FolderOpen`,
Voertuigen→`Car`, Assistant→`Bot`, Instellingen→`Settings`,
Admin→`ShieldCheck`. Icons render at a fixed size in both expanded and
collapsed states so the collapse transition doesn't visibly reflow icon
size.

**What stays untouched**: `Layout.tsx`'s mobile header, `MobileTabBar`,
`AlertsBell`, command-palette trigger, and the mobile drawer's
open/close/backdrop/escape behavior — none of this is in scope, only the
desktop sidebar's chrome and the new collapse affordance.

## Testing

- Extend `Sidebar.test.tsx`: collapse toggle flips width/localStorage,
  persisted state survives remount, icons render in both states, existing
  active-pill and mobile-drawer tests still pass unmodified.
- `Layout.test.tsx`: no behavior change expected, re-run as a regression
  check.
- Live-browser verification (per this project's standing convention — a
  passing test suite has repeatedly not been sufficient here, e.g. the
  Phase 5a/6a/6c findings): check expanded and collapsed states, light and
  dark mode, and the active-pill's position after a collapse/expand toggle
  on a real running instance, not just component tests.

## Open questions resolved during brainstorming

- **Scope**: confirmed to be app-shell-first (design system + sidebar/layout,
  then dashboard, documents, AI chat, login), landing/onboarding deferred to
  its own track, per explicit user choice over the alternative of starting
  with the landing page or jumping straight to dashboard/AI chat.
- **Brand mark**: no existing asset — confirmed building a new inline SVG
  mark rather than blocking on the user supplying artwork.
- **Nav item list**: the original brief's example menu (Dashboard,
  Documenten, AI Chat, Taken, Dossiers, Teams, Instellingen — 7 items) is
  shorter than the app's actual 11 nav items, and "Teams" doesn't
  correspond to any existing concept (the closest is Cases' workspace
  sharing). Treating the brief's list as illustrative, not a literal
  trim-down instruction: Legal draft/Calendar/Entities/Vehicles/Assistant
  are real shipped features, and removing them from nav would hide access
  to working functionality as a side effect of a styling pass. This spec
  keeps all current nav items and adds an icon to each; a deliberate
  information-architecture change (e.g. grouping into sections, demoting
  low-traffic items into a "More" overflow) is a candidate for the
  dashboard-redesign spec if the sidebar feels crowded once icons are in,
  not decided here.
