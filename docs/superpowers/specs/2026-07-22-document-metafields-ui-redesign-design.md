# Document Metafields + UI Redesign — Design Spec

**Sub-project 3 of the CollaBrains premium-SaaS redesign** (design system+sidebar and
dashboard+activity-timeline already shipped; this is next). Scope was narrowed from the
original "Documents redesign" ask via user confirmation on 2026-07-22: this spec covers
metafields extraction + the UI that renders them. Calendar auto-sync and address-model
consolidation are deliberately deferred to their own later sub-projects.

## Goal

Give every processed document a structured, per-doc-type set of extracted fields
(payslip → gross/net salary/period; invoice → amount/due date/invoice number; etc.),
stored queryably, and rendered generically in the document UI — closing the gap where
the current app only shows a handful of fixed columns (`doc_type`, `tags`,
`correspondent`) no matter what the document actually contains.

## Background / research findings

A comparison against the reference v2 checkout (`~/Downloads/cbrains-v2`) found:

- v2 stored a single freeform JSON blob (`Document.extracted_fields`) per document,
  populated by one big prompt, and rendered generically via `Object.entries()` in the
  frontend drawer. No schema, no validation.
- Current (`services/api/src/api/models.py`) has **no equivalent** — `Document` has only
  fixed typed columns. Structured facts that do exist are scattered: `Task`,
  `Entity`/`EntityMention`, `UserFact` (closest analog, but scoped to user-level facts,
  not document metadata).
- Current's classification pipeline (`document_classification.py`) is already better
  architected than v2's monolithic prompt: a dedicated, schema-constrained LLM call via
  `chat_completion(..., schema=...)`, triggered by its own event handler, auditable via
  `classification_confidence`. This spec follows that same pattern rather than v2's.
- Auto-categorization is already fully solved (`document_categories.py`,
  `document_classification.py`) — no changes needed there.
- Addresses are **out of scope**: current (`AddressDetail`, correspondent columns on
  `Document`) is already more relational than v2 ever was. Consolidating the two
  existing address shapes into one canonical model is real but separate follow-up work.
- Calendar sync (documents → `Appointment` rows) is a real, confirmed gap — but
  independent of metafields, and deferred per user's explicit sequencing choice.

## Scope

**In scope:**
1. `Document.metafields` JSONB column + per-doc-type field catalog + validation.
2. New extraction module + event wiring, following the existing classification/entity/
   task-extraction pattern.
3. API exposure of `metafields` on document detail.
4. Frontend: generic metafields card on the document detail page, with a per-field
   `.ics` download link for date-typed fields (cheap add-on; does *not* imply calendar
   auto-sync, which stays deferred).
5. Frontend: upgrade the flat category filter chips in the document list to a grouped
   parent/child view using the existing `DOCUMENT_CATEGORIES` taxonomy and this
   session's design-system tokens (glass surfaces, gradient accents).

**Out of scope (explicitly deferred to later sub-projects):**
- Address model consolidation (`AddressDetail` + correspondent columns → one `Address`
  model).
- Calendar auto-sync (document-detected dates/action-items auto-creating `Appointment`
  rows).
- Inline PDF preview (currently opens the file separately via `previewDocumentFile`) —
  flagged as an optional stretch during design review; not pulled into this spec.
- Any change to entity/task/classification extraction behavior itself.

## Architecture

A new module, `document_metafields.py`, mirrors the existing
`document_classification.py` pattern exactly:

- One schema-constrained LLM call via `api.ai_gateway.chat_completion(..., schema=...)`,
  same as `classify_document`.
- Its own event handler, subscribed to `EventType.DOCUMENT_CLASSIFIED` (not
  `EMBEDDINGS_CREATED`) — this event already carries `doc_type` in its payload
  (`documents.py:286`, published by `_handle_classify_document` after
  `classify_and_persist` runs), which is exactly what's needed to pick the right field
  schema before extraction. Chaining off `DOCUMENT_CLASSIFIED` avoids a race against
  classification and avoids re-deriving doc_type independently.
- Gated by a new settings flag, `auto_extract_metafields_on_ready: bool = True`
  (`config.py`, same pattern as `auto_classify_on_ready`/`auto_extract_facts_on_ready`).
- Graceful degradation on unparseable model output (return `None`/leave `metafields`
  unset), same as every other extraction module — a bad LLM response must never crash
  the document pipeline.

Extraction is **not** folded into `classify_document`'s existing call. Keeping it
separate preserves the current architecture's advantage over v2 (small, independently
auditable, independently failing extraction steps) and keeps `classification_confidence`
meaningful on its own.

## Data model

```python
# models.py, Document class
metafields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

New migration (alembic, chained off the current head at execution time).

New field catalog in `document_metafields.py`:

```python
DOC_TYPE_METAFIELD_SCHEMA: dict[str, list[str]] = {
    "payslip": ["gross_salary", "net_salary", "period"],
    "invoice": ["amount", "due_date", "invoice_number"],
    "bank_statement": ["account_number", "period", "closing_balance"],
    # ... one entry per doc_type in document_categories.DOC_TYPE_TO_CATEGORY_SLUG,
    # finalized during planning against the full VALID_DOC_TYPES set and v2's
    # "Canonieke veldnamen per documenttype" catalogue (ai.py:1-111 in the v2 checkout)
    # as a starting reference, adapted to English field names for consistency with
    # document_categories.py's existing English-slug convention.
}
```

Each field's type (string vs. date vs. number) is declared alongside its name so the
frontend can render dates specially (the `.ics` link) without string-sniffing. Exact
per-field type list is a planning-time detail, not pinned here.

Values are validated against the doc_type's declared field list before being persisted
— unknown keys from the LLM are dropped, not stored, keeping `metafields` predictable
enough to query (`WHERE metafields->>'invoice_number' = ...`) even though it's JSONB.

## Backend API

`documents.py`:
- `DocumentDetailOut` gains `metafields: dict | None`.
- `GET /documents/{id}` (existing handler) includes it — no new endpoint needed, this
  is an additive field on an existing response.

## Frontend

**`DocumentDetail.tsx`** — new card (same `Card` component, same placement pattern as
the existing "Classification" card at line 210-238), rendering `doc.metafields`
generically:

```tsx
{doc.metafields && Object.keys(doc.metafields).length > 0 && (
  <Card>
    <h2 className="text-sm font-medium text-ink-2">{t("documentDetail.metafields")}</h2>
    <div className="mt-2 flex flex-col gap-2">
      {Object.entries(doc.metafields).map(([key, value]) => (
        <div key={key} className="flex items-center justify-between text-sm">
          <span className="text-ink-3">{humanizeFieldKey(key)}</span>
          <span className="text-ink">{String(value)}</span>
          {isDateLikeKey(key) && <a href={buildFieldIcsUrl(doc.id, key)}>...</a>}
        </div>
      ))}
    </div>
  </Card>
)}
```

`humanizeFieldKey`/`isDateLikeKey` are new small helpers (snake_case → Title Case;
date-ness determined from the field catalog's declared type, exposed to the frontend via
a new `GET /categories/metafield-schema` lookup or a duplicated small constant —
finalized during planning).

**`Workspace.tsx`** — the existing flat `CATEGORY_FILTER_OPTIONS`/`FilterChips` block
(lines ~264-268) is replaced with a grouped view: parent categories from
`DOCUMENT_CATEGORIES` (already fetched as `CategoryOut[]` via `listCategories()`) shown
as a top row, each expandable/filterable to its child doc-type chips, styled with
`bg-gradient-brand`/`glass-surface`/`rounded-ds-*` tokens from sub-project 1. This is
additive to the existing filter mechanism (`categoryFilters` state, `activeCategoryFilters`
matching), not a rewrite of the filtering logic itself.

## Testing

- `services/api/tests/test_document_metafields.py` — unit tests for the extraction
  module (prompt construction, schema validation, malformed-output graceful
  degradation), mirroring `test_document_classification.py`.
- `services/api/tests/test_document_metafields_events.py` — event-wiring test
  (`DOCUMENT_CLASSIFIED` → extraction runs → `Document.metafields` populated), mirroring
  `test_document_classification_events.py`.
- `apps/web/src/routes/DocumentDetail.test.tsx` — new cases for the metafields card
  (renders when present, hidden when absent/empty, humanizes keys, shows `.ics` link
  for date fields).
- `apps/web/src/routes/Workspace.test.tsx` — new cases for the grouped category filter.

## Risks / open items for planning

- Exact per-doc-type field catalog (names + types) needs to be finalized against the
  full `VALID_DOC_TYPES` set during plan-writing — this spec establishes the pattern,
  not the exhaustive list.
- Whether the field-type metadata (for date detection) ships as a new small API
  endpoint or a frontend-side constant mirroring the backend catalog is a planning-time
  call, not architecturally significant either way.
