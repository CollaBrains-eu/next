# 0063 — Violet Design Language: production-readiness audit + backlog

## Status

Accepted

## Context

The user asked for an autonomous, phased pass ("audit → prioritized
backlog → execute P0 through P2, small PRs, no waiting for approval per
step") to turn the "CollaBrains — Violet Design Language" artifact
(`docs/design/violet-design-language.html`) into a production-ready
deliverable.

Before scoping any work, two things from ADR 0044 needed re-confirming
against current reality, since generic "make this production-ready"
instructions don't account for them:

1. **The artifact is deliberately not the shipped product.** ADR 0044
   archived it "verbatim ... since it's a design reference document, not
   part of the built app" and built real, tested primitives in
   `apps/web/src/components/ui/` instead. That directory now has 20
   paired `.tsx`/`.test.tsx` components (`Alert`, `Avatar`, `Badge`,
   `Breadcrumbs`, `BulkActionBar`, `Button`, `Combobox`, `CommandPalette`,
   `DataTable`, `Drawer`, `Dropdown`, `FilterChips`, `InlineEditableText`,
   `KanbanBoard`, `Modal`, `ShortcutsSheet`, `Skeleton`, `SplitView`,
   `Stepper`, `Tooltip`) — confirming the real productization path for
   this design language is the React app, not the HTML file itself.
2. **The artifact has grown since ADR 0044.** Re-fetching the live
   `claude.ai` artifact (137,294 bytes / 2,155 lines) and diffing it
   against the repo's archived copy showed them byte-identical except for
   a per-session iframe bootstrap script — so the archive is currently in
   sync — but the live artifact now has 26 sections vs. ADR 0044's "~24
   cataloged," including several added after that ADR: Typography,
   Icons, Multi-select combobox, Breadcrumbs, Stepper, Alerts, Avatars,
   Chat, Kanban (now real, see ADR 0045), document diff/redline,
   Deadlines & Reminders, Appointments (calendar + `.ics` export),
   a notification bell, and a keyboard-focus demo.

Given (1), "production-ready" for the parts of this design language that
require new data models (Chat, diff/redline, Deadlines & Reminders,
Appointments) means a real backend phase, exactly as ADR 0044 predicted
for Kanban — which then *did* need `Task.position` + a migration + a
status-whitelist change (ADR 0045). Attempting to fake that integration
inside a static HTML artifact would be scope creep and would not
actually make anything production-ready. Those stay explicitly deferred.

What *is* legitimately this artifact's own responsibility — because nothing
else in the repo owns it — is the artifact being correct, accessible, and
usable **as the reference document it's archived to be**, especially since
its own footer says "Tell me if it's ready to lock in as the spec" and
explicitly lists its own gaps: "domain-specific components (real plate
input, case-status pipeline, styled metadata display), mobile-specific
patterns, and a WCAG contrast audit."

### Audit findings

Full read of all 2,155 lines plus live verification in a connected Chrome
tab (served over `http://127.0.0.1` — `file://` is blocked by the
extension) at 1280px and 375px viewports:

- **No responsive design exists anywhere.** The only `@media` rule in the
  file is `prefers-reduced-motion`. Confirmed live: at 375px, the header's
  four action controls (notification bell, "Simulate navigation",
  "⌘ Search", "Dark mode") don't wrap and run off the right edge of the
  viewport — **Dark mode toggle and Search become completely unreachable
  on a phone**, not just visually cramped.
- **Zero accessibility semantics.** `grep -c 'aria-\|role='` across the
  whole file returns 0. Icon-only buttons (🔔 ⋯ ✎ ✕ 👁 ⬇ 🗑 ‹ ›) rely only
  on a `title` attribute, which most screen readers don't reliably expose
  as an accessible name. Modal/drawer/command-palette/dropdown overlays
  have no `role="dialog"`/`aria-modal`, no focus trap, and no
  `aria-expanded` on their triggers. The toast layer has no `aria-live`.
- **Quantified WCAG contrast failures** (computed via the actual relative-
  luminance formula against the real token hex values, light mode):
  - `--text-3` (`#9CA3AF`) on `--bg-card`: **2.54:1**; on `--bg`: **2.24:1**
    — needs 4.5:1 for normal text. This token is used pervasively (swatch
    hex labels, `meta-row` keys, timeline entries, `type-label`,
    `space-label`, `agenda-time`, notification meta text) — the single
    biggest-blast-radius failure in the file.
  - `--accent` on `--accent-bg` (badge/secondary-button text): 3.71:1 —
    fails for the 11–14px sizes actually used.
  - `--success` on `--success-bg`: 3.00:1 — fails.
  - `--danger` on `--bg-card` (form `.err-msg` text — real validation
    error copy): 3.76:1 — fails, and is the highest-consequence one since
    it's literally the "why did my form submission fail" text.
- **Self-declared, still-open backlog** (from the artifact's own footer):
  a real Dutch kenteken plate input, a case-status pipeline component, and
  a styled metadata display — all pure frontend, no backend dependency.

## Decision

Prioritized backlog, ordered P0→P3. P0/P1 are executed in this pass as
small, independently reviewable PRs against `docs/design/` (and
`apps/web/src/components/ui/` for P1's real components); P2 is attempted
if time allows; P3 is explicitly deferred with rationale, matching the
ADR 0044/0045 precedent for Kanban.

**P0 — breaks core usability or fails a hard compliance bar**
1. Mobile responsiveness: header wraps, app-shell sidebar/kanban/table
   adapt below ~640px, verified live at 375px and 768px.
2. WCAG AA contrast: retune `--text-3`, `--accent`-on-`--accent-bg`,
   `--success`-on-`--success-bg`, `--danger`-on-`--bg-card` to ≥4.5:1 (or
   justify 3:1 only where the real rendered text is confirmed large/bold),
   reverified by computed ratio in both themes.
3. Accessibility semantics: `aria-label` on icon-only controls,
   `role="dialog"`/`aria-modal`/focus handling on overlays,
   `aria-expanded` on disclosure triggers, `aria-live="polite"` on toasts.

**P1 — self-declared backlog, pure frontend, no backend dependency**
4. `PlateInput` — Dutch kenteken format/mask, mirrors the app's real RDW
   integration.
5. `CaseStatusPipeline` — status-flow component distinct from the generic
   `Stepper`, reusing the existing case-status vocabulary.
6. `MetadataList` — a reusable styled key/value block, replacing the
   ad hoc `meta-row` markup duplicated across the drawer/table-detail/
   split-view code paths.
   Built as tested React components in `apps/web/src/components/ui/`
   following the exact ADR 0044 shape (paired `.tsx`/`.test.tsx`, one real
   page wired as integration proof) — these are genuinely part of the
   *product*, not the reference doc.

**P2 — polish, lower urgency**
7. In-page section navigation (26 sections / 2,155 lines with no way to
   jump to one) — quality-of-life for a document whose whole purpose is
   being referenced.
8. Minor source hygiene: the static "Details" panel markup in the initial
   drawer HTML duplicates the `docDetailsHtml` template string the JS
   swaps in on open; the keyboard-focus demo's `<a href="#"
   onclick="return false;">` is a pattern real code shouldn't copy.

**P3 — explicitly deferred, needs its own backend-design phase**
9. Turning Chat, document diff/redline, Deadlines & Reminders, and
   Appointments/Calendar into real `apps/web` features. Each needs new
   data models and endpoints comparable in scope to what Kanban actually
   required (ADR 0045: `Task.position`, a migration, a status-whitelist
   change) — attempting this inside an autonomous artifact-polish pass
   would be an unreviewed scope expansion, not a fix.

Every artifact edit is applied to the live `claude.ai` artifact (the
thing the user actually opened this conversation to edit) and then synced
verbatim into `docs/design/violet-design-language.html`, preserving the
ADR 0044 "archive mirrors the live spec" convention.

## Consequences

- The archived copy and the live artifact stay in lockstep; anyone
  reading `docs/design/violet-design-language.html` sees exactly what's
  published at the artifact URL.
- P1's three new primitives extend the same
  `apps/web/src/components/ui/` catalog ADR 0044 started, rather than
  living only inside the reference document.
- P3 remains an explicit, scoped follow-up rather than a silently-skipped
  or silently-attempted piece of work.
