# Document Metafields Coverage Expansion — Design Spec

**Follow-up to `2026-07-22-document-metafields-ui-redesign-design.md`** (the metafields
extraction system itself, already shipped: `Document.metafields` JSONB column,
`document_metafields.py` extraction module, generic metafields card in the UI). This spec
extends that system's coverage — it does not change its architecture.

## Goal

Close two real gaps found by comparing `document_metafields.DOC_TYPE_METAFIELD_SCHEMA`
against `document_categories.DOCUMENT_CATEGORIES`:

1. Several real-world document types people actually receive have no `doc_type` value at
   all today, so they fall into `other` and get zero metafields (receipts, subscriptions,
   prescriptions, lab results, warranties).
2. A few existing schemas are thin relative to what's realistically extractable
   (`contract`, `medical`, `care`, `policy`/`insurance`).

Every *currently declared* taxonomy `doc_type` already has a metafield schema except
`other` (intentional — it's the unclassified catch-all) — so this is additive coverage
work, not a backfill of a broken system.

## Scope

**In scope:**

1. Five new `doc_type` values, each folded into an **existing** category (no new category
   slugs, so no i18n changes needed — `doc_type` itself is rendered as a raw string in
   `DocumentDetailContent.tsx`, only category slugs are translated):
   - `receipt` → `invoice` category. Fields: `vendor`, `amount`, `purchase_date` (date).
   - `subscription` → `invoice` category. Fields: `provider`, `monthly_amount`,
     `renewal_date` (date).
   - `prescription` → `medical_care` category. Fields: `medication`, `dosage`,
     `prescribing_doctor`, `issue_date` (date).
   - `lab_result` → `medical_care` category. Fields: `test_name`, `result_summary`,
     `test_date` (date).
   - `warranty` → `other_documents` category. Fields: `product`, `vendor`,
     `warranty_expiry_date` (date).
2. Additive fields on four existing schemas (no field removal/rename — purely additive,
   so no migration of already-extracted historical `metafields` values is needed):
   - `contract` (employment contracts): + `position`, `salary`, `notice_period`.
   - `medical`: + `diagnosis`, `next_appointment_date` (date).
   - `care`: + `care_type`.
   - `policy`, `insurance`: + `coverage_amount`, `renewal_date` (date), `deductible`.
3. Test coverage: extend `test_document_metafields.py` for the 5 new doc_types (schema
   lookup, extraction parsing, date-field detection) and the 4 deepened schemas: confirm
   old + new field keys all round-trip through `_parse_metafields`/`is_date_field`.

**Out of scope:**

- The pre-existing empty `rental_contract` category (`doc_types: []` in
  `document_categories.py`). Populating it risks new classification ambiguity against
  `housing`/`contract` and is a taxonomy decision, not a metafields one — leaving as a
  known quirk, same deferral pattern the original spec used for address consolidation.
- Any change to the classification prompt/logic in `document_classification.py` — new
  `doc_type` values are automatically classifiable once added to `VALID_DOC_TYPES`
  (derived from `DOCUMENT_CATEGORIES`), since `CLASSIFICATION_SCHEMA`'s `doc_type` enum
  is built from that set at import time. No prompt wording changes needed.
- Any frontend change beyond what already exists — the metafields card already renders
  whatever keys are present generically (`Object.entries`-style), and the `.ics` export
  already derives date-kind fields from `is_date_field()`. New/expanded fields need zero
  new frontend code.
- New categories or i18n strings — deliberately avoided by folding all 5 new doc_types
  into existing categories.

## Data flow (unchanged from the shipped system)

`document_classification.py` assigns `doc_type` (grammar-constrained to
`VALID_DOC_TYPES`) → the existing post-classification event handler calls
`extract_and_persist_metafields(doc_type=...)` → `document_metafields.py` looks up
`DOC_TYPE_METAFIELD_SCHEMA[doc_type]`, builds a JSON-schema-constrained
`chat_completion` call, parses/persists the result to `Document.metafields` → frontend
renders it generically. This spec only adds entries to `DOCUMENT_CATEGORIES` (taxonomy)
and `DOC_TYPE_METAFIELD_SCHEMA` (field catalog) — every downstream step already handles
new keys with no code change.

## Known limitation (accepted, not new)

Some classification fuzziness is expected between related doc_types (e.g. `receipt` vs.
`invoice`, `prescription` vs. `medical`). The existing taxonomy already tolerates this
exact class of overlap today (`payslip`/`salary`/`annual_statement` are near-synonyms and
already coexist as separate doc_types) — this spec extends an already-accepted tradeoff,
not a new risk category. Not gating this work on classification-prompt tuning.

## Testing

Same pattern as the shipped metafields system: unit tests in
`test_document_metafields.py` covering schema lookup and parsing for each new/changed
doc_type, no new integration surface (extraction event wiring is unchanged). No live
deploy verification plan changes — same rsync-to-server pytest gate this project already
uses, per `docs/superpowers/plans/2026-07-22-document-metafields-ui-redesign.md`'s
established pattern.
