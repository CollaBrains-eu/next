# 0055 — i18n pass round 2: Documents, Cases, Tasks, Vehicles

## Status

Accepted

## Context

Follow-on to the i18n foundation (ADR 0051), which translated only the
nav shell. This round translates actual page content for four of the
highest-traffic pages, continuing the same `labelKey` + `t()` pattern
and the same three-locale (`en`/`nl`/`de`) structure.

## Decision

- Extended `apps/web/src/locales/{en,nl,de}.json` with four new
  namespaces (`documents`, `cases`, `tasks`, `vehicles`) plus a few
  more `common` entries (`loading`, `cancel`, `delete`, `create`) that
  are reused across pages rather than duplicated per-namespace.
- Used i18next's built-in pluralization (`_one`/`_other` key suffixes)
  for count-dependent strings (`documents.results`,
  `documents.deletedToast`) and interpolation (`{{count}}`,
  `{{date}}`, `{{name}}`, `{{filter}}`) for the rest — no extra
  library/config needed, this is standard i18next behavior already
  available from the ADR 0051 setup.
- **`Workspace.tsx`** (the `/` route, the Documents page): heading,
  search form (label/placeholder/button/clear), result count, empty
  state, all three `DataTable` column headers, all three status-filter
  chip labels, the bulk-delete action label, and the delete-count
  toast.
- **`Cases.tsx`**: heading, "New case" button (reused for both the
  trigger button and the create-form's own label), Cancel/Create
  buttons, name/description placeholders, empty state, and the two
  error messages.
- **`Tasks.tsx`**: heading, the three status-filter button labels
  (`open`/`done`/`all` — kept lowercase in translation, matching the
  original literal values so existing tests didn't need touching),
  List/Board view toggle, the empty-state message (with the active
  filter interpolated in), due-date/assignee/source-document labels on
  each task row, and all three error messages. Added `t` to the
  `refresh` callback's `useCallback` dependency array — this is
  correct, not just satisfying the linter: when the language changes,
  `t`'s reference changes, which should re-trigger `refresh` so a
  freshly-fetched error (if any) renders in the new language too.
- **`Vehicles.tsx`**: **partial by design** — translated the heading,
  loading state, empty state, and error messages, but deliberately
  left "Zoek op" (the lookup button) and all the RDW field labels
  (`Merk / model`, `Voertuigsoort`, `Kleur`, `APK-vervaldatum`,
  `WAM-verzekerd`, `Nog niet opgehaald.`, `Geen RDW-gegevens gevonden
  voor dit kenteken.`) as hardcoded Dutch, untouched. These are
  official Dutch vehicle-registry (RDW) terminology, not generic UI
  chrome — treating them like "IBAN" or other domain-specific terms
  that don't get translated regardless of UI language, consistent with
  how a French banking app wouldn't translate "IBAN" into English. Not
  wrapped in `t()` at all (no pointless single-value translation keys
  where the value is identical across all three locales anyway).

## Verification

- Full frontend suite (live `web` container): 48 files / 217 tests
  passed, unchanged from before this round — every string I translated
  either wasn't asserted on by an existing test, or the English
  translation is byte-identical to what was previously hardcoded (e.g.
  `tasks.filterDone` → `"done"`, matching the existing
  `getByRole("button", { name: "done" })` assertion exactly).
- **Real browser verification with actual live language switching**,
  not just English defaults: a throwaway QA admin session with
  `preferred_language` set to `Nederlands` in Postgres loaded all four
  pages fresh (with a hard reload each time, having learned from ADR
  0054 that same-session navigation can serve a stale cached bundle)
  and confirmed every translated string rendered correctly in Dutch —
  including the pluralized/interpolated ones (`Vervalt op {date}`,
  `Toegewezen aan: {name}`) and the deliberately-untouched RDW field
  labels still showing their original Dutch text as designed.

## Consequences

- 4 of the remaining ~50 files now have real page-content translation,
  on top of the nav shell from ADR 0051. `DocumentDetail`, `CaseDetail`,
  `Entities`, `EntityGraph`, `EntityReview`, `AdminDashboard`, `Chat`,
  `Legal`, `Assistant`, `Settings`, `Login`, and the shared
  components (`UploadDialog`, `DataTable`'s own chrome, `Card`,
  `EmptyState`'s default message, etc.) are still English-only —
  someone with `preferred_language=Nederlands` browsing e.g. Documents
  → Entities will see a page flip from fully Dutch to fully English.
  This is the same honest scope boundary ADR 0051 flagged, just moved
  four pages further, not closed.
- The RDW-terminology scoping decision (leave Dutch, don't wrap in
  `t()`) sets the pattern for any other genuinely domain-specific,
  non-UI-chrome text found in later rounds — worth applying
  consistently rather than re-litigating per page.
