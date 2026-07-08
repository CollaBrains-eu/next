# Phase 20: Violet Design Language & Frontend Motion System

## Status
Approved (brainstorming)

## Context

A production audit (2026-07-08) found `v78281.1blu.de` technically
healthy -- all containers up, TLS/backups/monitoring green -- but
visually and functionally rough: the Documents/Cases/Vehicles lists
were flooded with leftover test-fixture rows from Phases 16-19's own
development (dozens of duplicate plates, a case literally titled "A
test matter for Phase 17b verification"), with no pagination anywhere
to contain it. Separately, two independent Codeberg repos
(`support-cb/Cbrains-v2`, `support-cb/Cbrains-v3`) turned out to hold
earlier, parallel attempts at this same product, neither of which is a
fork of this repo. `Cbrains-v2` (595 commits, real disaster-recovery
docs, its own CI, its own mobile app) has a genuinely deliberate,
named design system ("CollaBrains -- Violet design system" per its own
`index.css` comment) -- a violet/lavender identity with Notion-style
muted text hierarchy, iOS-style card shadows, and real polish
components (`CollaButton`, `CollaCard`, `CollaBadge`,
`MagneticButton`, `FloatingCard`, a command palette).
`Cbrains-v3` uses a similar violet-family primary but a generic,
unbranded zinc/shadcn-style neutral palette with no named component
system -- read as an unfinished reskin, not a distinct identity.

This phase's goal is narrower than a full frontend rebuild: define and
validate a complete design language -- tokens, components, motion, and
core interaction patterns -- before any of it is wired into the live
`apps/web` frontend. The actual frontend integration is deliberately
**not** part of this phase; it's the next `writing-plans` cycle.

App Store/Play Store distribution (originally Phase 4 of the
post-audit action plan) is explicitly deferred, at the user's request,
in favor of this design pass.

## Decision

**Base the design language on Cbrains-v2, not v3, and not a blend.**
v2 is the more complete, deliberately-branded system with a real
component library and evidence of actual production use (disaster
recovery runbook, nightly automation). v3's plainer palette is treated
as a minor footnote only -- its accent hue (`#7c3aed`) is in the same
violet family, which is worth noting as a coincidental signal that
"violet" is this product's genuine brand color across independent
attempts, but nothing else from v3 was adopted.

**Design tokens are CSS custom properties, light+dark, matching v2's
actual values verbatim where they exist:**

```
--bg: #F0EFFF          --bg (dark): #0D0C1A
--bg-sidebar: #ffffff  --bg-sidebar (dark): #13112A   (deliberately lighter than --bg -- elevation, not a bug)
--bg-card: #ffffff     --bg-card (dark): #13112A
--text: #1E1B4B        --text (dark): rgba(255,255,255,.90)
--text-2: #6B7280      --text-2 (dark): rgba(200,195,255,.65)
--text-3: #9CA3AF      --text-3 (dark): rgba(200,195,255,.38)
--accent: #6C63FF      --accent (dark): #8B82FF
--success: #16A34A     --warning: #D97706   --danger: #EF4444   (dark-mode variants brightened for contrast)
```

Typography: Inter (sans, UI), IBM Plex Mono (mono, data/identifiers --
plates, dates, IDs). Base body 15px/1.6, `xs` 11.5px for meta/labels.
Numeric table columns use `font-variant-numeric: tabular-nums` so
columns of dates/plates align.

**New foundation tokens not present in v2, added this phase:**
a 4px-base spacing scale (4/8/12/16/24/32/48/64) and a 4-level
elevation scale (flat / raised / overlay / modal, each a named
`box-shadow` token) -- v2 had ad-hoc spacing and only two elevation
levels (flat card, hover card), which wasn't enough foundation for a
component library this size.

**Motion tokens and principles**, layered on top of v2's identity (v2
had `framer-motion` micro-interactions but no documented motion
system): `--ease-out` (`cubic-bezier(.16,1,.3,1)`) for page/section
entrances and staggered list reveals; `--ease-spring`
(`cubic-bezier(.34,1.56,.64,1)`) for buttons, the sliding nav-active
indicator, toasts, and modals/drawers; linear timing only for
cursor-tracked hover effects (card tilt, magnetic buttons). All motion
respects `prefers-reduced-motion` -- JS-driven effects (tilt, magnetic
pull, circular theme-switch reveal) no-op entirely under it, matching
how v2's own `MagneticButton`/`FloatingCard` already behaved.

**Component library**, table-stakes tier (all with light/dark and,
where relevant, hover/focus/error/disabled states): buttons (primary/
secondary/ghost/danger, 3 sizes, ripple + press feedback), badges
(default/success/warning/danger, with a pulsing-dot "processing" state
that morphs into a checkmark-draw "ready" state), cards (tilt-on-hover,
staggered entrance), skeleton loading shimmer, form inputs (text,
select, checkbox, toggle switch, inline validation error), a sortable
data table with pagination, an empty state (animated blob illustration
+ one action), a slide-in detail drawer with tabs (mirrors v2's real
`DocumentDrawer`/`EntityDrawer` pattern), a generic confirm modal,
dropdown menu, tooltip, toast (including an undo-able variant), a
command palette (`⌘K`, adapted from v2's real `CommandPalette`,
supports live filtering and arrow-key navigation), a keyboard-shortcuts
sheet (`?`), a global top-of-viewport loading bar, and a sliding
active-item indicator for sidebar navigation.

**Core interaction patterns validated this phase**, chosen because the
production audit or the component review surfaced a concrete need for
each: bulk selection (row checkboxes → floating action bar) and filter
chips directly address the "unbounded, unfiltered list" problem found
in the audit; a global loading bar addresses AI-chat response times of
~15-20s (per prior load-testing notes) reading as a hang; inline
editing (click a pencil, edit in place, save-flash confirmation)
avoids a separate edit mode/page for simple fields; a split-view layout
toggle (inline detail pane beside the list, vs. the default overlay
drawer) is included as a wide-screen-friendly alternative, with the
overlay drawer remaining the default.

**Every interactive element was implementation-tested, not just
described.** The working prototype (an HTML/CSS/vanilla-JS artifact,
no framework, no external dependencies -- CSP-safe) was driven
end-to-end with Playwright across three rounds of user feedback. This
caught two functional gaps where a control looked interactive but had
no handler wired (an empty-state "New case" button, and a set of five
further dead controls: command palette items, the row-actions dropdown,
the bulk bar's Export button, pagination prev/next, and table sort,
which only flipped its arrow icon without reordering rows) and two
runtime bugs: an inline-edit crash from a `blur` handler re-firing on
an already-detached input, and dark-mode table text staying stuck at
the light-mode color due to a Chromium quirk where `<table>`'s
anonymous box model doesn't reliably re-cascade an *inherited* (not
explicitly declared) `color` after a runtime CSS-custom-property
change -- fixed by declaring `color` explicitly on `td` rather than
relying on inheritance through the table. All of this is fixed in the
current prototype, which is the source of truth for exact markup/CSS/
JS -- this document records the decisions and rationale, not a
byte-for-byte spec of the prototype's code.

## Open Questions Resolved

- **Which of the two Codeberg repos to base this on?** v2, not v3 or a
  blend -- see Decision above. User confirmed after seeing both
  summarized and after reviewing the v2-based mockup.
- **How much motion is appropriate for a legal/insurance-adjacent
  tool?** User reviewed the full motion system (tilt, spring physics,
  circular theme transitions, staggered entrances) applied to realistic
  content (Dutch vehicle plates, case names, document lists) and did
  not ask for it to be toned down -- confirmed via silence/approval
  after an explicit prompt, not assumed.
- **What functions does the language need beyond static components?**
  User asked for "everything" from a suggested list (bulk selection,
  filter chips, global loading bar, inline editing, keyboard shortcuts,
  split view) -- all six were built and are part of this spec, not
  deferred.
- **Does it actually work, or does it just look right?** Explicitly
  re-tested after the user twice reported dead controls ("New case"
  showing nothing; "not all functions are working"). Resolved by a
  full audit cross-referencing every clickable element against its
  event wiring, not incremental spot-checks -- see Decision above for
  what that found.

## Consequences

- **Deferred, not solved, by explicit scope choice**: domain-specific
  components this product will need but which weren't designed this
  phase -- a real license-plate input with country selector and
  validation state (the audit found a half-built one: disabled search
  button, raw `<dl>`-style RDW output), a case-status pipeline visual,
  and a styled metadata key-value display (vehicle/entity attributes
  currently render as a plain definition list). Candidate for its own
  focused design pass.
- **Mobile-specific adaptation is not designed here**: bottom sheets
  instead of centered modals on small screens, 44px minimum touch
  targets, and reviving the swipe-to-delete pattern noted from an
  earlier CollaBrains build are all still open. `apps/mobile` exists
  (Phase 7) but this design language was validated against the web
  layout only.
- **No WCAG contrast audit performed.** The palette was carried over
  from v2 largely as-is; `--text-3` on `--bg` in particular (light gray
  on light lavender) has not been measured against WCAG AA and may
  fail it. Worth auditing before this ships broadly, not blocking this
  spec.
- **App Store/Play Store distribution remains deferred** (originally
  Phase 4 of the post-audit action plan), at the user's explicit
  request, in favor of this design pass. Still blocked on the same
  gaps noted in that plan: the existing `apps/mobile` scaffold was
  deliberately built test-only (ADR 0016), native in-app-purchase is
  required by both stores for in-app subscriptions, and the user's own
  Apple/Google developer accounts are needed.
- **This spec does not change any code in `apps/web` or `apps/mobile`.**
  It validates the design in an isolated prototype. Applying these
  tokens/components/patterns to the real frontend -- including
  reconciling them with whatever `apps/web` currently does for
  theming, and deciding whether to introduce `framer-motion` as a
  dependency (as v2 did) vs. hand-rolling the vanilla-JS approach the
  prototype uses -- is the next phase, planned separately via
  `writing-plans`.
