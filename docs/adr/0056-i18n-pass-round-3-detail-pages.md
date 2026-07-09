# 0056 — i18n pass round 3: DocumentDetail, CaseDetail, Entities, EntityReview

## Status

Accepted

## Context

Follow-on to ADR 0055 (Documents/Cases/Tasks/Vehicles). This round
translates the four pages most directly linked from those: the two
detail/drill-down views (`DocumentDetail`, `CaseDetail`) and the
entity-extraction workflow (`Entities`, `EntityReview`). Same
`labelKey` + `t()` pattern, same three-locale (`en`/`nl`/`de`)
structure, four new namespaces added to
`apps/web/src/locales/{en,nl,de}.json`: `documentDetail`,
`caseDetail`, `entities`, `entityReview`.

## Decision

- **`DocumentDetail.tsx`**: breadcrumb, load/summarize/delete error
  messages, summarize button's three states, processing-error alert,
  summary/extracted-text section headings, the mime/status/chunk-count
  line (chunk count now pluralized via `_one`/`_other` instead of the
  old hardcoded `chunk(s)`), and the full delete-confirmation modal
  (title interpolates the document title, body, cancel/confirm
  buttons, toast). Reused `common.delete`/`common.cancel`/`common.loading`
  and `nav.documents` (for the breadcrumb) rather than duplicating
  strings already in those namespaces.
- **`CaseDetail.tsx`**: breadcrumb, loading/error states, the four
  section headers (`Documents`/`Tasks`/`Vehicles` reuse the existing
  `nav.*` keys since the text is identical; `Decisions` is new — no
  nav entry exists for it), the "+ Attach"/"Attach"/"Select…" attach
  controls, and the "Nothing linked yet." empty state shared across
  all four sections.
- **`Entities.tsx`**: heading, description, search placeholder, both
  filter dropdowns (type and status), the "Review pending →" link,
  and the empty state.
- **`EntityReview.tsx`**: back link, heading, "Approve all", the
  "{{current}} of {{total}}" progress line (interpolated), empty
  state, Approve/Reject buttons, and the keyboard-shortcut hint.
- **Deliberately left untranslated, in both `Entities.tsx` and
  `EntityReview.tsx`: the entity's `entity_type` badge/label**
  (`person`/`organization`/`vehicle`/etc.), which renders the raw
  backend enum value directly. This is data, not UI chrome — same
  class of decision as the RDW field labels in ADR 0055 and the task
  status parenthetical in `CaseDetail.tsx`'s linked-task rows (also
  left untranslated here, for the same reason). Translating it would
  require introducing a shared type→label lookup used consistently
  across both files' badge renderers, which is a real piece of design
  work on its own — worth doing later as a deliberate follow-up, not
  as a side effect of this pass. It's also what the existing test
  suite asserts on directly (`getByText("person")`,
  `getByText("organization")`), so leaving it alone kept this round's
  diff focused on net-new translation rather than a test rewrite.

## Verification

- Full frontend suite (live `web` container, freshly rsynced): 48
  files / 217 tests passed, unchanged.
- `pnpm exec vite build` succeeded, producing a fresh content-hashed
  bundle.
- Real browser verification via Playwright against a throwaway QA
  admin session (`preferred_language=Nederlands`, cleaned up after):
  loaded all four pages fresh and confirmed correct Dutch rendering,
  including interpolation (`"3 fragmenten"`, `"1 van 50"`) and the
  full delete-confirmation modal flow on `DocumentDetail` (opened,
  read the interpolated title and body text, cancelled without
  deleting the real document).

## Consequences

- 8 of the remaining ~50 files now have real page-content translation
  (4 from ADR 0055, 4 from this round). `AdminDashboard`, `Chat`,
  `Legal`, `Assistant`, `Settings`, `Login`, `NotFound`, and the
  shared chrome components are still English-only — same honest scope
  boundary as before, moved four pages further.
- The "raw domain/data value stays untranslated" pattern now has three
  independent instances (RDW fields, task status, entity type badges)
  across two rounds — worth treating as an established project
  convention rather than a per-page judgment call going forward.

## Unrelated finding

While setting up browser-based QA verification, `https://collabrains.eu/`
was found to be unreachable: its DNS `A` record resolves to
`178.254.22.178`, which is a different IP than this session's server
(`v78281.1blu.de` / `195.90.216.230`) and refuses connections on port
443 entirely — confirmed from two independent networks. This is
unrelated to the i18n work and outside this session's SSH access
(DNS/registrar-level, not server-level); flagged to the user directly
in chat rather than investigated further here.
