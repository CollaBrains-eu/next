# 0059 — Document categories: v2 taxonomy port, auto-categorization, filter UI

## Status

Accepted

## Context

The existing document classifier (Phase 23) used a flat, 5-value
`doc_type` enum (`invoice|contract|correspondence|legal|other`) with no
grouping. CollaBrains v2 (`support-cb/Cbrains-v2` on Codeberg) had a
much richer, hierarchical taxonomy — 6 parent categories, ~19
subcategories, ~25 rows total — that this plan
(`docs/superpowers/plans/2026-07-10-document-categories.md`) ports into
the rebuild, adapted to this project's stack (SQLAlchemy async,
Alembic, FastAPI, react-i18next) instead of v2's.

Four tasks executed this plan in sequence:

1. **Schema + seed** (`c41c49e`) — generic, self-referential
   `Category` table (`category_type` discriminator, so the same table
   can hold non-document taxonomies later without a new table),
   `documents.category_id` FK, and the full 25-row taxonomy seeded
   atomically inside the migration.
2. **Auto-categorization** (`ebc79c5`) — the single existing
   classification AI call now offers the full ~25-value `doc_type`
   enum instead of 5, and `classify_and_persist` maps the returned
   `doc_type` to a `category_id` via a static `DOC_TYPE_TO_CATEGORY_SLUG`
   dict (mirroring v2's `tasks.py` pattern), falling back to
   `other_documents` for anything unmapped. No new AI call, no new
   architecture.
3. **`GET /categories`** (`45400ab`) — read-only lookup endpoint
   returning `{id, slug, icon, color, parent_id}`, deliberately
   omitting `name`.
4. **Frontend** (this ADR) — i18n'd display names + a second
   `FilterChips` row on `Workspace.tsx`.

## Decision

**i18n names instead of hardcoded strings.** v2 baked Dutch category
names directly into its seed data. This project already has a working
`react-i18next` setup (`apps/web/src/locales/{en,nl,de}.json`), so
`Category.name` on the backend stays populated with the slug itself
(an English identifier, used only as an admin-facing/LLM-facing
fallback) and is never sent over the wire — `categories_router.py`'s
`CategoryOut` omits `name` entirely, specifically so it can't
accidentally get rendered instead of the localized label. The frontend
derives the display string via `t(\`categories.${category.slug}\`)`
against a new 25-key `categories` namespace added to all three locale
files. The Dutch (`nl.json`) names are the original v2 wording,
restored rather than freshly translated; German (`de.json`) is a new
translation, consistent with how prior i18n-pass ADRs (0055/0056/0058)
have handled languages v2 never shipped.

**`api.ts`**: added `CategoryOut` and `listCategories(categoryType =
"document")`, following the existing `request<T>(path, init)` /
`listDocuments()`-style pattern already in the file. Added
`category_id: string | null` to `DocumentOut` (the backend column has
existed since Task 1; the frontend type just hadn't caught up).

**`Workspace.tsx`**: added `categories`/`categoryFilters` state, a
`listCategories()` effect on mount, and `CATEGORY_FILTER_OPTIONS`
computed the same way `STATUS_FILTER_OPTIONS` already is. The
`filteredDocuments` memo now ANDs the existing status condition with a
category condition (`activeCategoryFilters.size === 0 ||
(doc.category_id !== null && activeCategoryFilters.has(doc.category_id))`),
so an empty category-filter selection is a no-op, matching the
existing status-filter's empty-selection behavior. The second
`FilterChips` row is rendered **only when `categories.length > 0`**
— not unconditionally as the plan's illustrative pseudocode suggested.
Rendering it unconditionally would put two "+ Add filter" buttons on
screen from the very first paint (before the category list has
loaded), which breaks every pre-existing test that queries
`screen.getByText("+ Add filter")` unscoped (they'd suddenly match two
elements) and is also poor UX — a filter row with zero addable options
serves no purpose. Gating on `categories.length > 0` keeps all
pre-existing tests passing unmodified and only introduces the second
row once it's actually usable.

**Tests**: two new cases in `Workspace.test.tsx` — selecting a category
chip narrows the table, and removing it restores the full list — reusing
the file's actual fixture conventions (the `docs` array, not the
plan's illustrative `DOC_FIXTURE` placeholder name, which doesn't exist
in this file). Both wait for `screen.getAllByText("+ Add filter")` to
reach length 2 before interacting with the category row, rather than
assuming a fixed microtask-resolution order between the `listDocuments`
and `listCategories` effects.

## Verification

- **Test execution**: `pnpm`/`node_modules` are not available in this
  worktree (no lockfile-installed dependencies present), so
  `pnpm exec vitest run` could not be executed directly. Verified by
  careful manual trace of `Workspace.test.tsx` against the final
  `Workspace.tsx` implementation instead — the same fallback method
  used for this session's backend tasks when live infra wasn't
  reachable. All 9 tests in the file (7 pre-existing + 2 new) were
  traced instruction-by-instruction against component state
  transitions and confirmed to produce the expected DOM assertions.
- **Live verification** (container rebuild, migration against the live
  database, real Playwright check of an uploaded document getting a
  category chip and the chip actually narrowing the list): not
  performed by this task — no subagent in this session has had
  Docker/live-container access. This is deferred to one consolidated
  live-verification pass the orchestrator runs at the end of the full
  project (covering both the MAM and document-categories tracks
  together), matching how every other task's live-infra step was
  handled this session.

## Consequences

- The document-categories plan is now fully closed out: taxonomy,
  auto-categorization, read API, and filter UI all shipped.
- `DocumentDetail.test.tsx`'s `mockDoc` fixture was not updated to
  include `category_id` — it's out of this task's file scope (the
  plan's Task 4 file list didn't include it) and doesn't affect
  runtime test behavior since Vitest/esbuild doesn't type-check, but a
  future `tsc --noEmit` pass would flag it as missing the newly-required
  `DocumentOut` field.
- The consolidated live-verification pass (see above) still owes a
  real end-to-end check: upload → classify → category chip appears →
  filtering by it narrows the table against a live backend, not just
  the unit-test trace done here.
