# 0051 — i18n foundation: framework, locale files, nav shell translated

## Status

Accepted

## Context

The user's requirement: the UI language must follow the same setting
that already controls AI response language (`UserPreference.
preferred_language`), not a separate UI-only picker. That setting
already existed (ADR-era Phase, `preferences.py`) and already drove
`build_language_instruction`'s prompt injection for legal drafts, chat,
and the manager agent — but the frontend had zero i18n infrastructure
(no library, no translation files, every string hardcoded English).

Full app-wide translation across ~50 files is the single largest item
from the original request — genuinely comparable in scope to the whole
Fase-1 backend marathon earlier this session. Rather than attempt it
in one unscoped pass, built the foundation (framework, wiring, the one
`preferred_language` setting driving both AI and UI language) and
translated the highest-visibility, always-on-screen surface (the nav
shell) as a working, fully-verified proof — leaving the remaining
~50 files as explicitly flagged, not silently incomplete.

## Decision

- `i18next` + `react-i18next` installed (`pnpm add`, live in the `web`
  container, package.json/pnpm-lock.yaml synced back).
- `apps/web/src/lib/i18n.ts` — the i18next instance, inline `resources`
  (no lazy-loaded backend — three languages, small key set so far,
  no need for the added complexity), default/fallback `en`.
- `apps/web/src/locales/{en,nl,de}.json` — nav labels + a handful of
  common strings (sign out, dark/light mode toggle, open-menu label).
- **`LANGUAGE_NAME_TO_CODE`** (`i18n.ts`): maps the *existing* stored
  `preferred_language` values (`"English"`, `"Nederlands"`, `"Deutsch"`
  — natural-language names, because they're injected directly into an
  LLM prompt) to i18next locale codes (`en`/`nl`/`de`). Deliberately did
  **not** change the stored format or add a migration — preserves
  whatever real users already have saved, and keeps
  `build_language_instruction`'s AI-facing behavior untouched.
- **`syncLanguage()`** (`lib/auth.tsx`) — the single function that
  actually calls `i18n.changeLanguage()`. Called from two places: once
  in `AuthProvider` after a user is loaded (fetches `getPreferences()`,
  syncs on login/page load), and once in `Settings.tsx`'s save handler
  (syncs immediately after a successful save, no reload needed). One
  setting, one sync function, two call sites — not a separate UI
  language picker anywhere.
- Translated: `Sidebar.tsx` (all nav labels, sign out, dark/light mode
  toggle), `Layout.tsx` (mobile hamburger's "Open menu" aria-label),
  `CommandCenter.tsx` (the ⌘K palette's "Go to {page}" entries, which
  also consume `NAV_ITEMS` and needed the same `label` → `labelKey`
  + `t()` change `Sidebar` got). `navigation.ts`'s `NAV_ITEMS` changed
  from `{to, label}` to `{to, labelKey}` — the single source of truth
  both `Sidebar` and `CommandCenter` render through.
- `apps/web/vitest.setup.ts` imports `./src/lib/i18n` globally so every
  test file gets a working, initialized i18next instance without
  needing to import it individually.

## Verification

- Full frontend suite (live `web` container): 48 files / 217 tests
  passed — 6 new tests: 2 in `Sidebar.test.tsx` proving nav labels
  actually change language when `i18n.changeLanguage("nl"/"de")` is
  called, 4 in a new `auth.test.ts` for `syncLanguage`'s mapping
  (`Nederlands`→`nl`, `Deutsch`→`de`, `null`→`en`, and an unrecognized
  value defaulting to `en` rather than throwing).
- **Real browser verification**, not just tests: a throwaway QA user
  with `preferred_language` set directly in Postgres to `"Nederlands"`
  loaded the live site and the entire nav rendered in Dutch
  (Documenten, AI-chat, Juridisch concept, Taken, Entiteiten, Zaken,
  Voertuigen, Assistent, Instellingen, Afmelden, Donkere modus) with
  zero console errors — confirming the on-login sync path.
  Separately, on the live Settings page, switching the dropdown to
  "Deutsch" and clicking Save **instantly** re-rendered the sidebar in
  German with no page reload — confirming the save-time sync path
  independently from the login-time one.
- Test QA user, its preferences row, and the browser session were
  cleaned up afterward.

## Consequences — scope boundary, explicitly not closed

This is a foundation, not app-wide localization. Translated: the nav
shell only (Sidebar, mobile header, command palette). **Not
translated**: every page's own headings, labels, buttons, empty
states, form fields, error messages — the ~50 route/component files
this touches are still 100% hardcoded English. Anyone landing on, say,
the Documents page with `preferred_language=Nederlands` will see a
Dutch sidebar around an English page. This is the expected, visible
boundary of this pass — not a bug, but a real limitation to communicate
clearly rather than let "i18n foundation shipped" be read as "the app
is localized."

Follow-up (not started): translate the remaining ~50 files' strings
page by page, following the same `labelKey` + `t()` pattern established
here; decide whether to keep translation keys inline per-file or
consolidate them further as the key count grows.
