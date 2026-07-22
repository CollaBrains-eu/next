# Document Metafields Coverage Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 new document types (receipt, subscription, prescription, lab_result,
warranty) to the existing metafields system, and deepen 4 existing thin schemas
(contract, medical, care, policy/insurance) — purely additive data changes to the
already-shipped metafields extraction system, no new architecture.

**Architecture:** No new modules, endpoints, or migrations. `Document.metafields` is
already a JSONB column (schemaless — new dict keys need no schema migration).
`document_classification.py`'s `doc_type` enum is already derived at import time from
`document_categories.DOCUMENT_CATEGORIES`, so adding a doc_type string to an existing
category's `doc_types` list makes it immediately classifiable with zero prompt changes.
`document_metafields.py`'s `DOC_TYPE_METAFIELD_SCHEMA` dict is the single source of
truth the extraction call and the frontend's date-detection (`is_date_field`) both read
from — adding/extending entries there is the entire "extraction" side of the change.
The frontend metafields card and `.ics` export already render whatever keys are
present generically — no frontend code changes in this plan.

**Tech Stack:** FastAPI + async SQLAlchemy + pytest (backend only, matches the spec's
explicit "no frontend changes" scope).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-22-document-metafields-coverage-expansion-design.md`.
- No local Postgres/Docker in this dev environment — `services/api` is bind-mounted
  into the live server's `api` container at `/opt/collabrains`, server
  `root@178.254.22.178`. Every backend test run requires an rsync-to-server round
  trip, then `docker compose exec -T api uv run pytest ...` — this is the same
  pattern used by every prior sub-project this session (`2026-07-22-document-metafields-ui-redesign.md`,
  `2026-07-22-calendar-auto-sync.md`). Do not run `pytest` locally.
- Disposable-test-user pattern: every new test creates its own uniquely-suffixed user
  (`f"{base}-{uuid4().hex[:8]}"`, via the existing `_unique()` helper in
  `test_document_metafields.py`) — the test Postgres is shared, not
  transaction-isolated across runs.
- No Alembic migration in this plan — `Document.metafields` (JSONB) already exists;
  new field names inside it are a Python-side data change only.
- Out of scope (do not touch, per the spec): `document_classification.py`'s prompt
  text, the empty `rental_contract` category's `doc_types` list, any frontend file,
  any new category slug or i18n string.

---

### Task 1: Add 5 new doc_types (taxonomy + metafield schema)

**Files:**
- Modify: `services/api/src/api/document_categories.py:22` (`invoice` category),
  `:37-38` (`medical_care` category), `:60-61` (`other_documents` category)
- Modify: `services/api/src/api/document_metafields.py:30` (insert new entries near
  the existing `"invoice"` line), `:38-39` (near `"medical"`/`"care"`)
- Create: `services/api/tests/test_document_categories.py`
- Modify: `services/api/tests/test_document_metafields.py`

**Interfaces:**
- Consumes: `DOC_TYPE_METAFIELD_SCHEMA` (existing dict in `document_metafields.py`),
  `DOCUMENT_CATEGORIES`/`DOC_TYPE_TO_CATEGORY_SLUG`/`VALID_DOC_TYPES` (existing in
  `document_categories.py`, `VALID_DOC_TYPES`/`DOC_TYPE_TO_CATEGORY_SLUG` are computed
  from `DOCUMENT_CATEGORIES` at import time — no separate update needed once
  `DOCUMENT_CATEGORIES` changes).
- Produces: five new valid `doc_type` string values (`receipt`, `subscription`,
  `prescription`, `lab_result`, `warranty`) usable by any later task or by
  `document_classification.py` (unmodified) and `document_metafields.py`
  (unmodified extraction logic — only its data dict changes).

- [ ] **Step 1: Write the failing taxonomy test**

Create `services/api/tests/test_document_categories.py`:

```python
from api.document_categories import DOC_TYPE_TO_CATEGORY_SLUG, VALID_DOC_TYPES

NEW_DOC_TYPE_CATEGORIES = {
    "receipt": "invoice",
    "subscription": "invoice",
    "prescription": "medical_care",
    "lab_result": "medical_care",
    "warranty": "other_documents",
}


def test_new_doc_types_are_valid_and_mapped_to_the_expected_category():
    for doc_type, category_slug in NEW_DOC_TYPE_CATEGORIES.items():
        assert doc_type in VALID_DOC_TYPES
        assert DOC_TYPE_TO_CATEGORY_SLUG[doc_type] == category_slug
```

- [ ] **Step 2: Run the test to verify it fails**

Run (via the rsync-to-server round trip):
`docker compose exec -T api uv run pytest tests/test_document_categories.py -v`
Expected: FAIL — `receipt`/`subscription`/`prescription`/`lab_result`/`warranty` not
in `VALID_DOC_TYPES`.

- [ ] **Step 3: Add the new doc_types to the taxonomy**

In `services/api/src/api/document_categories.py`, change line 22 from:

```python
    {"slug": "invoice", "icon": "Receipt", "color": "#FF3B30", "parent": "finance", "doc_types": ["invoice"]},
```

to:

```python
    {"slug": "invoice", "icon": "Receipt", "color": "#FF3B30", "parent": "finance",
     "doc_types": ["invoice", "receipt", "subscription"]},
```

Change lines 37-38 from:

```python
    {"slug": "medical_care", "icon": "HeartPulse", "color": "#5AC8FA", "parent": "insurance_care",
     "doc_types": ["medical", "care"]},
```

to:

```python
    {"slug": "medical_care", "icon": "HeartPulse", "color": "#5AC8FA", "parent": "insurance_care",
     "doc_types": ["medical", "care", "prescription", "lab_result"]},
```

Change lines 60-61 from:

```python
    {"slug": "other_documents", "icon": "File", "color": "#8E8E93", "parent": "other_group",
     "doc_types": ["other", "legal"]},
```

to:

```python
    {"slug": "other_documents", "icon": "File", "color": "#8E8E93", "parent": "other_group",
     "doc_types": ["other", "legal", "warranty"]},
```

- [ ] **Step 4: Run the taxonomy test again to verify it passes**

Run: `docker compose exec -T api uv run pytest tests/test_document_categories.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing metafield-schema tests**

Append to `services/api/tests/test_document_metafields.py` (after the existing
`test_is_date_field_identifies_declared_date_fields` function):

```python
from api.document_metafields import DOC_TYPE_METAFIELD_SCHEMA

NEW_DOC_TYPE_FIELDS = {
    "receipt": {"vendor", "amount", "purchase_date"},
    "subscription": {"provider", "monthly_amount", "renewal_date"},
    "prescription": {"medication", "dosage", "prescribing_doctor", "issue_date"},
    "lab_result": {"test_name", "result_summary", "test_date"},
    "warranty": {"product", "vendor", "warranty_expiry_date"},
}


def test_new_doc_types_have_the_declared_metafield_schema():
    for doc_type, expected_fields in NEW_DOC_TYPE_FIELDS.items():
        actual_fields = {name for name, _ in DOC_TYPE_METAFIELD_SCHEMA[doc_type]}
        assert actual_fields == expected_fields


async def test_extract_metafields_parses_a_new_doc_type_receipt():
    user = await _create_user(_unique("metafieldreceiptuser"))
    fake = '{"vendor": "Albert Heijn", "amount": "23.40", "purchase_date": "2026-07-20"}'
    with patch("api.document_metafields.chat_completion", AsyncMock(return_value=fake)):
        result = await extract_metafields(doc_type="receipt", text="receipt text", user_id=user.id)

    assert result == {"vendor": "Albert Heijn", "amount": "23.40", "purchase_date": "2026-07-20"}


def test_is_date_field_identifies_new_doc_type_date_fields():
    assert is_date_field("receipt", "purchase_date") is True
    assert is_date_field("subscription", "renewal_date") is True
    assert is_date_field("prescription", "issue_date") is True
    assert is_date_field("lab_result", "test_date") is True
    assert is_date_field("warranty", "warranty_expiry_date") is True
    assert is_date_field("receipt", "vendor") is False
```

- [ ] **Step 6: Run the new tests to verify they fail**

Run: `docker compose exec -T api uv run pytest tests/test_document_metafields.py -v -k "new_doc_type or receipt"`
Expected: FAIL — `KeyError` on the five new doc_types (not yet in
`DOC_TYPE_METAFIELD_SCHEMA`).

- [ ] **Step 7: Add the new doc_type schemas**

In `services/api/src/api/document_metafields.py`, change line 30 (the `"invoice"`
entry) from:

```python
    "invoice": [("amount", "string"), ("due_date", "date"), ("invoice_number", "string")],
```

to:

```python
    "invoice": [("amount", "string"), ("due_date", "date"), ("invoice_number", "string")],
    "receipt": [("vendor", "string"), ("amount", "string"), ("purchase_date", "date")],
    "subscription": [("provider", "string"), ("monthly_amount", "string"), ("renewal_date", "date")],
```

Change lines 38-39 (the `"medical"`/`"care"` entries) from:

```python
    "medical": [("provider", "string"), ("visit_date", "date")],
    "care": [("provider", "string"), ("visit_date", "date")],
```

to:

```python
    "medical": [("provider", "string"), ("visit_date", "date")],
    "care": [("provider", "string"), ("visit_date", "date")],
    "prescription": [
        ("medication", "string"), ("dosage", "string"), ("prescribing_doctor", "string"), ("issue_date", "date"),
    ],
    "lab_result": [("test_name", "string"), ("result_summary", "string"), ("test_date", "date")],
```

Add a `"warranty"` entry at the end of the dict, immediately before the closing `}`
(after the existing `"legal"` line):

```python
    "warranty": [("product", "string"), ("vendor", "string"), ("warranty_expiry_date", "date")],
```

- [ ] **Step 8: Run the new tests to verify they pass**

Run: `docker compose exec -T api uv run pytest tests/test_document_metafields.py tests/test_document_categories.py -v`
Expected: PASS — all tests including the pre-existing ones in
`test_document_metafields.py`.

- [ ] **Step 9: Commit**

```bash
git add services/api/src/api/document_categories.py services/api/src/api/document_metafields.py \
  services/api/tests/test_document_categories.py services/api/tests/test_document_metafields.py
git commit -m "feat: add receipt/subscription/prescription/lab_result/warranty doc types"
```

---

### Task 2: Deepen 4 existing thin schemas (contract, medical, care, policy/insurance)

**Files:**
- Modify: `services/api/src/api/document_metafields.py:36-40` (`policy`, `insurance`,
  `medical`, `care`, `contract` entries — Task 1's insertions shift these down by a
  few lines each; locate each by its `"policy":`/`"medical":`/`"contract":` key text,
  not the line number)
- Modify: `services/api/tests/test_document_metafields.py`

**Interfaces:**
- Consumes: `DOC_TYPE_METAFIELD_SCHEMA` (same dict Task 1 extended — this task only
  adds fields to four pre-existing keys, does not touch Task 1's five new keys).
- Produces: no new public names — `contract`/`medical`/`care`/`policy`/`insurance`
  keep their existing dict keys, just with more tuples in each value list.

- [ ] **Step 1: Write the failing schema-shape tests**

Append to `services/api/tests/test_document_metafields.py`:

```python
DEEPENED_DOC_TYPE_FIELDS = {
    "contract": {"counterparty", "start_date", "end_date", "position", "salary", "notice_period"},
    "medical": {"provider", "visit_date", "diagnosis", "next_appointment_date"},
    "care": {"provider", "visit_date", "care_type"},
    "policy": {"policy_number", "provider", "premium", "coverage_amount", "renewal_date", "deductible"},
    "insurance": {"policy_number", "provider", "premium", "coverage_amount", "renewal_date", "deductible"},
}


def test_deepened_doc_types_have_the_expanded_metafield_schema():
    for doc_type, expected_fields in DEEPENED_DOC_TYPE_FIELDS.items():
        actual_fields = {name for name, _ in DOC_TYPE_METAFIELD_SCHEMA[doc_type]}
        assert actual_fields == expected_fields


async def test_extract_metafields_parses_the_new_contract_fields():
    user = await _create_user(_unique("metafieldcontractuser"))
    fake = (
        '{"counterparty": "Acme BV", "start_date": "2026-01-01", "end_date": null, '
        '"position": "Software Engineer", "salary": "65000", "notice_period": "1 month"}'
    )
    with patch("api.document_metafields.chat_completion", AsyncMock(return_value=fake)):
        result = await extract_metafields(doc_type="contract", text="contract text", user_id=user.id)

    assert result["position"] == "Software Engineer"
    assert result["salary"] == "65000"
    assert result["notice_period"] == "1 month"


def test_is_date_field_identifies_new_date_fields_on_deepened_doc_types():
    assert is_date_field("medical", "next_appointment_date") is True
    assert is_date_field("policy", "renewal_date") is True
    assert is_date_field("insurance", "renewal_date") is True
    assert is_date_field("medical", "diagnosis") is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec -T api uv run pytest tests/test_document_metafields.py -v -k "deepened or new_contract or deepened_doc_types"`
Expected: FAIL — the assertion sets don't match yet (e.g. `contract` is still missing
`position`/`salary`/`notice_period`).

- [ ] **Step 3: Deepen the four schemas**

In `services/api/src/api/document_metafields.py`, find the `"policy"`/`"insurance"`
lines (originally lines 36-37, now shifted down by Task 1's insertions — locate by
key text) and change:

```python
    "policy": [("policy_number", "string"), ("provider", "string"), ("premium", "string")],
    "insurance": [("policy_number", "string"), ("provider", "string"), ("premium", "string")],
```

to:

```python
    "policy": [
        ("policy_number", "string"), ("provider", "string"), ("premium", "string"),
        ("coverage_amount", "string"), ("renewal_date", "date"), ("deductible", "string"),
    ],
    "insurance": [
        ("policy_number", "string"), ("provider", "string"), ("premium", "string"),
        ("coverage_amount", "string"), ("renewal_date", "date"), ("deductible", "string"),
    ],
```

Find the `"medical"`/`"care"` lines and change:

```python
    "medical": [("provider", "string"), ("visit_date", "date")],
    "care": [("provider", "string"), ("visit_date", "date")],
```

to:

```python
    "medical": [("provider", "string"), ("visit_date", "date"), ("diagnosis", "string"), ("next_appointment_date", "date")],
    "care": [("provider", "string"), ("visit_date", "date"), ("care_type", "string")],
```

Find the `"contract"` line and change:

```python
    "contract": [("counterparty", "string"), ("start_date", "date"), ("end_date", "date")],
```

to:

```python
    "contract": [
        ("counterparty", "string"), ("start_date", "date"), ("end_date", "date"),
        ("position", "string"), ("salary", "string"), ("notice_period", "string"),
    ],
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec -T api uv run pytest tests/test_document_metafields.py -v`
Expected: PASS — every test in the file, including all of Task 1's and the
pre-existing ones.

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `docker compose exec -T api uv run pytest -v`
Expected: PASS, or only the same pre-existing unrelated failures already documented
in this project's history (test-DB pollution class — see
`project-collabrains` memory) — no *new* failures caused by this change. If any
new failure appears, stop and investigate before continuing (systematic-debugging,
not a guess-and-patch).

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/document_metafields.py services/api/tests/test_document_metafields.py
git commit -m "feat: deepen contract/medical/care/policy/insurance metafield schemas"
```

---

### Task 3: Deploy and live-verify

**Files:** none (deploy + verification only, no code changes)

**Interfaces:** none — this task exercises the already-committed changes from Tasks 1-2
against the live stack.

- [ ] **Step 1: Push to origin/main**

```bash
git push origin main
```

- [ ] **Step 2: Pull on the server and confirm the backend picked it up**

Run (on `root@178.254.22.178`):

```bash
cd /opt/collabrains && git pull
docker compose logs api --tail 20
```

Expected: log shows `WatchFiles detected changes... Reloading...` shortly after the
pull (uvicorn `--reload` picks up the change automatically — no rebuild/restart
needed, per this project's established deploy pattern). No frontend deploy step is
needed (no frontend files changed in this plan).

- [ ] **Step 3: Live-verify one new doc_type end-to-end**

Upload (or re-classify, if a suitable existing test document is available) a real
receipt-like document through the live app, and confirm via the API that
`doc_type` is one of the new values and `metafields` contains the new schema's keys:

```bash
docker compose exec -T api uv run python -c "
import asyncio
from api.db import async_session
from api.models import Document
from sqlalchemy import select

async def main():
    async with async_session() as db:
        result = await db.execute(
            select(Document).where(Document.doc_type.in_(
                ['receipt', 'subscription', 'prescription', 'lab_result', 'warranty']
            )).limit(5)
        )
        for doc in result.scalars():
            print(doc.id, doc.doc_type, doc.metafields)

asyncio.run(main())
"
```

If no live document has naturally classified into one of the five new types yet
(expected on a first check — classification only runs on new uploads), this step is
a no-op confirmation that the query runs cleanly; do not force-classify an existing
document just to make this print something. The real verification is Steps 4-5 of
Task 1 and Task 2 already having passed against the live-server test suite in
Steps 2/4/5 above — this step is a bonus real-world sanity check, not the primary
gate.

- [ ] **Step 4: Confirm no regressions in the full suite one more time post-pull**

Run: `docker compose exec -T api uv run pytest -v`
Expected: same pass/fail shape as Task 2 Step 5 (no new failures from the deploy
itself).
