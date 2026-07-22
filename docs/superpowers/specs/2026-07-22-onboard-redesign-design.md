# Onboard Redesign — Design Spec

**Sub-project 6 of the CollaBrains premium-SaaS redesign** (design system+sidebar,
dashboard+activity-timeline, documents metafields+UI, calendar auto-sync, AI
chat redesign, and login redesign already shipped). Brings the same visual
language and routing fix applied to `/login` to `/onboard`, the invite-token
confirmation page.

## Background

This sub-project was originally scoped as "Landing page + onboarding flow."
Reading `Landing.tsx` in full during planning found it already fully built,
polished, and animated (574 lines: hero, feature grids, pricing tiers,
enterprise section, AI demo, IP-based language detection) — and it carries an
explicit code comment (`Landing.tsx:116-117`) declaring its dark theme
deliberate: *"Marketing splash for anonymous visitors... deliberately
dark/animated, distinct from the light Violet DS app shell authenticated users
see."* This predates and is intentionally distinct from the current
design-token redesign track. The user confirmed: leave `Landing.tsx`
untouched, scope this sub-project to `Onboard.tsx` only.

`Onboard.tsx` is in the same position `Login.tsx` was before its own
redesign: a plain old `Card` (`rounded-2xl border border-edge bg-surface`),
no brand identity, and registered inside `AppShell`'s `<Layout>`
(`App.tsx:65`, `<Route path="/onboard" element={<Onboard />} />`) — so an
anonymous visitor following an invite link sees the full app `Sidebar` and
mobile chrome around the onboarding card, the same bug just fixed for
`/login`.

## Scope

**In scope:**
1. Move `/onboard` out of `<Layout>` onto its own standalone top-level route
   in `App.tsx`, alongside `/login` — no `Sidebar`, no mobile header, no
   `MobileTabBar`.
2. Restyle `Onboard.tsx`'s card with the same shell `Login.tsx` now uses:
   `glass-surface`, `rounded-ds-lg`, `BrandMark` + the "Collabr**AI**ns"
   gradient wordmark, inside a full-viewport centered wrapper — applied
   uniformly across all three of `Onboard`'s states (`loading` /
   `SkeletonLines`, `valid`, `invalid`).

**Out of scope:**
- `Landing.tsx` — confirmed deliberately distinct, not touched.
- `checkOnboardingToken`, state handling, or any other logic in
  `Onboard.tsx` — visual/routing changes only.
- Button gradient treatment: unlike `Login.tsx`'s single primary submit
  button, `Onboard.tsx`'s CTA is contextual (primary "Continue to sign in"
  on success, secondary on failure) — no single button warrants the
  `bg-gradient-brand` treatment the way Login's submit did, so button
  styling is left as-is.
- `TextField`/`Select`/other shared form components, `Button.tsx`,
  `Card.tsx` — same reasoning as the Login spec: out of scope, and (per the
  Login plan's Global Constraints) an appended `rounded-ds-lg` does not
  reliably override `Button`'s built-in `rounded-xl` in this Tailwind setup.
- i18n keys — no copy changes, existing `onboard.*` keys reused as-is.

## Architecture

No backend changes. Two frontend files:

- `App.tsx`: add `<Route path="/onboard" element={<Onboard />} />` as a
  top-level sibling of `/login` (both now sit outside `AppShell`'s
  `<Layout>`), and remove it from `AppShell`'s own `<Routes>`.
- `Onboard.tsx`: replace the `Card`-wrapped return with the same
  `glass-surface`/`BrandMark` shell `Login.tsx` uses, wrapping all three
  status branches (`loading`, `valid`, `invalid`) in one consistent
  container instead of restyling each separately.

## Testing

- `Onboard.test.tsx`: existing 4 tests should keep passing unchanged
  (`getByRole("heading", ...)`, `getByRole("link", ...)` queries don't
  depend on className or the outer wrapper) — confirm at planning time.
- Live-browser verification (established practice): temporarily check
  `/onboard` with both a valid and an invalid/missing token, at desktop and
  mobile widths, confirming no `Sidebar`/`MobileTabBar` chrome and the new
  card styling; revert any test-only setup before finishing.

## Risks / open items for planning

- Exact placement of the new `<Route path="/onboard" .../>` relative to
  `/login` in `App.tsx`'s top-level `<Routes>` — planning-time call, trivial
  given Task 1 of the Login plan already established the pattern.
- Whether the `loading` (`SkeletonLines`) state needs any special handling
  inside the new shell, given it currently renders inside the same `Card`
  as the other two states — check during planning that `SkeletonLines`
  looks correct inside the new glass container.
