# Login Redesign — Design Spec

**Sub-project 5 of the CollaBrains premium-SaaS redesign** (design system+sidebar,
dashboard+activity-timeline, documents metafields+UI, calendar auto-sync, and AI
chat redesign already shipped). Brings the visual language established in
sub-project 1 (design tokens: `glass-surface`, `bg-gradient-brand`, `rounded-ds-*`,
`BrandMark`) to the `/login` page, and fixes a routing bug where it currently
renders inside the authenticated app shell.

## Background

`Login.tsx` predates this session's design-token work: a plain `Card`
(`rounded-2xl border border-edge bg-surface`), a bare `<h1>`, no brand identity.

Additionally, `/login` is currently registered inside `AppShell`'s `<Layout>`
(`App.tsx:63`), so `Sidebar` renders around it — `Sidebar.tsx:31` builds
`navItemsForRole(user?.role)` regardless of whether `user` exists, so an
unauthenticated visitor sees the full app navigation (Dashboard, Documents,
Chat, Tasks, ...) around the login card, plus the mobile header and
`MobileTabBar`. None of that chrome is meaningful pre-authentication — it's a
bug, not a feature, and it directly affects the page this sub-project
redesigns, so fixing it is in scope.

`Landing.tsx` (the marketing page at `/`) is a separate, bespoke dark-themed
page (`bg-zinc-950`, its own violet palette, `Sparkles` icon) that predates the
design-token system too and is an explicitly separate, not-yet-started track
("Landing page + onboarding flow"). This sub-project does not touch
`Landing.tsx` and does not attempt to visually match it — `/login` adopts the
same app design-token language already shipped to Dashboard/Documents/Chat/
Assistant, since functionally it's part of the authenticated app, not the
marketing site.

## Scope

**In scope:**
1. Move `/login` out of `<Layout>` onto its own standalone route in
   `App.tsx` — no `Sidebar`, no mobile header, no `MobileTabBar`. Full-viewport
   centered layout instead.
2. Restyle the login card with design tokens: `glass-surface`, `rounded-ds-lg`,
   the existing `shadow-raised` token.
3. Add brand identity: `BrandMark` + the "Collabr**AI**ns" gradient wordmark
   (same markup pattern as `Sidebar.tsx:58-67`) above the existing
   title/subtitle text.
4. Restyle the primary submit button with `bg-gradient-brand`.
5. Restyle the passkey button's corners to `rounded-ds-lg` (no behavior
   change).

**Out of scope:**
- `TextField`/`Select` and other shared form components — used across the
  whole app's forms; changing their radius/style is a much larger blast
  radius than a login-only redesign.
- Auth logic, new fields, password reset, social login, "remember me" — none
  requested, none needed.
- `/onboard`'s own `<Layout>`-wrapping (same class of issue, but not in scope
  for this sub-project — noted as a follow-up for the Landing+onboarding
  track).
- `Landing.tsx` itself — separate, not-yet-started track with its own
  bespoke aesthetic.
- i18n keys — no copy changes, existing `auth.*` keys are reused as-is.

## Architecture

No backend changes. Two frontend files:

- `App.tsx`: move the `<Route path="/login" element={<Login />} />` out of
  `AppShell`'s `<Layout>`-wrapped `<Routes>` block into its own top-level
  route, rendered without `Layout`. (Exact mechanics — e.g. a second
  top-level `<Routes>`/`<Route>` sibling to `AppShell`, or a conditional
  inside `AppShell` — is a planning-time call once the surrounding router
  structure is read in full.)
- `Login.tsx`: wrap the existing `Card` in a full-viewport centered flex
  container (`min-h-screen flex items-center justify-center bg-page`, or
  similar), swap `Card`'s className for the glass/token styling, add the
  `BrandMark`+wordmark block, update the submit `Button`'s className for the
  gradient. Existing state/handlers (`handleSubmit`, `handlePasskeyLogin`,
  `useAuth()`, `isPasskeySupported()`) are unchanged.

## Testing

- `Login.test.tsx`: existing 4 tests should keep passing structurally
  unchanged (`getByRole("heading", ...)`, `getByLabelText(...)`,
  `getByRole("button", ...)` queries don't depend on className or the outer
  wrapper) — the test already renders `<Login/>` standalone, not through
  `App.tsx`'s router, so the route-relocation shouldn't require test changes
  there; confirm at planning time.
- New/updated test if `App.tsx`'s routing structure changes in a way that's
  itself testable (e.g. an assertion that `/login` renders without the
  sidebar) — confirm whether a router-level test file exists at planning
  time and whether this is worth adding.
- Live-browser verification (established practice this session): temporarily
  override `useAuth()`, screenshot `/login` at desktop and mobile widths,
  confirm no `Sidebar`/`MobileTabBar` chrome appears and the card is
  centered; revert before finishing.

## Risks / open items for planning

- Exact `App.tsx` restructuring mechanics (top-level sibling route vs.
  conditional inside `AppShell`) — planning-time call, needs reading
  `App.tsx` in full, including how `RootRoute` and `AppShell` are wired at
  the top of the router tree.
- Whether a router-level test file (e.g. covering `App.tsx` directly) exists
  and needs updating for the route move — check at planning time.
