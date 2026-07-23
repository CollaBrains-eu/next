# 0071 — Priority 2, item 5: quality improvements

## Status

Accepted

## Context

ADR 0066 (Priority 2, item 5) asked to review and implement, where
justified, the quality gaps its own audit had already found: missing FK
indexes, ARIA problems, focus management, keyboard navigation, and
responsive issues. Each item below was re-verified before fixing, not
assumed correct from the original audit — two of the four turned out to
need correction.

## Decision

**Database indexes** — the audit flagged `documents.category_id`,
`documents.residency_id`, and `tasks.created_by` as unindexed FKs.
Re-checked while writing the migration: `category_id` already has an
index (migration `0026aa5966bf`, `create_categories_table` — the
audit's grep missed it because that migration adds the index inline in
`create_table` rather than via a standalone `op.create_index`). Only
`residency_id` and `created_by` were genuinely missing; migration
`f4e8b2a6c9d1` adds just those two.

**Focus trap + ARIA** — no overlay had a real focus trap before (only
Escape-to-close), and Drawer/CommandPalette had no `role="dialog"`/
`aria-modal` at all. A shared `useFocusTrap` hook
(`apps/web/src/hooks/useFocusTrap.ts`) now handles focus-in-on-open,
Tab/Shift+Tab cycling, and focus-restoration-on-close for Modal, Drawer,
and ShortcutsSheet. CommandPalette additionally gets the full ARIA
combobox pattern (`role="combobox"` + `aria-expanded`/`aria-controls`/
`aria-activedescendant` on the input, `role="listbox"`/`role="option"`/
`aria-selected` on the results) since it had zero `aria-*` despite being
the app's primary keyboard-driven search UI. Tooltip now wires
`aria-describedby` onto its trigger and reveals on `group-focus-within`
as well as `group-hover` — previously a keyboard-only user tabbing to a
tooltipped button never saw the label at all.

**Responsive fixes** — the audit flagged both `Workspace.tsx`
(`/documents`) and `Vehicles.tsx` for zero responsive breakpoint
classes. Re-checked before fixing: `Workspace.tsx`'s header row and
search form were genuinely unwrapped flex rows that could overflow at
phone width — fixed with this project's own established pattern for
this exact shape (ADR 0057: `flex-col`/`sm:flex-row` for page headers,
`flex-wrap` for inline control clusters). `Vehicles.tsx` turned out to
already use `flex-wrap` throughout — a valid, non-breakpoint-prefixed
responsive technique the audit's "count `sm:`/`md:`/`lg:` classes"
method structurally couldn't detect — so it needed no change. The
Playwright responsive suite (ADR 0069) is extended to cover
`Workspace.tsx` now that it's fixed, per that ADR's own note deferring
the assertion until this fix landed.

**Keyboard navigation** — covered by the focus-trap work above (Tab
cycling within every overlay) plus what already existed (Escape-to-close
on every overlay, arrow-key navigation already implemented in
CommandPalette).

## Consequences

- Two audit findings (the `category_id` index, `Vehicles.tsx`'s
  responsiveness) turned out to be false positives on closer inspection
  — corrected here rather than fixed unnecessarily, and noted so a
  future pass doesn't re-flag the same non-issues.
- The genuine findings (two missing indexes, five overlay components
  needing focus/ARIA work, one page's responsive overflow) are fixed and
  covered by tests (5 new hook tests, updated component tests, an
  extended Playwright spec).
- 548/548 frontend vitest tests pass, `pnpm lint` clean, the FK-index
  migration verified applying cleanly against a fresh database.
