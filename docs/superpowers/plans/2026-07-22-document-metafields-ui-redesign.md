# Document Metafields + UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every processed document a structured, per-doc-type set of extracted
fields (metafields), stored in a validated JSONB column, and render them generically
in the document UI — plus a grouped category-filter UI upgrade in the document list.

**Architecture:** A new `document_metafields.py` module mirrors the existing
`document_classification.py` pattern: one schema-constrained LLM call per document,
triggered by a dedicated event handler subscribed to `DOCUMENT_CLASSIFIED` (which
already carries `doc_type`). Extracted fields are validated against a per-doc-type
field catalog before being persisted to `Document.metafields` (JSONB). The frontend
renders `metafields` generically (humanized key/value list) and offers a per-field
`.ics` download for date-typed fields, reusing the existing `ics_utils` module. The
document list's category filter is upgraded from a flat chip list to a two-level
parent/child grid using the existing `DOCUMENT_CATEGORIES` taxonomy.

**Tech Stack:** FastAPI + async SQLAlchemy + pytest (backend); React + TypeScript +
Vitest/Testing Library (frontend); Alembic migrations; Ollama via `api.ai_gateway`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-22-document-metafields-ui-redesign-design.md`.
- No local Postgres/Docker in this dev environment — `services/api` is bind-mounted
  into the live server's `api` container. Every backend test run requires an
  rsync-to-server round trip, then `docker compose exec -T api uv run pytest ...`.
  Run `pytest` commands below via that round trip, not locally.
- Frontend verification: `vite build` is the real gate, not `tsc -b` (106 pre-existing,
  unrelated React 19/18 type errors). `eslint` is not installed in this checkout —
  skip linting.
- Frontend deploy requires an explicit
  `docker compose exec web sh -c 'cd /app/apps/web && npx vite build'` on the server —
  `docker compose up -d web` alone does not rebuild the frontend.
- Backend deploy is automatic via uvicorn `--reload` — no manual restart needed after
  `git pull` on the server.
- Disposable-test-user pattern: every test creates its own uniquely-suffixed user
  (`f"{base}-{uuid4().hex[:8]}"` or a numbered literal already unique in the file) —
  the test Postgres is shared and not transaction-isolated across runs.
- Current alembic head at plan-writing time: `e1a5c9f3b7d2`
  (`add category to tasks`). Verify this hasn't changed before writing Task 1's
  migration — if it has, update `down_revision` accordingly.
- Addresses and calendar auto-sync (`Appointment` row creation) are explicitly out of
  scope for every task below — do not touch `AddressDetail`, `Residency`, or
  `Appointment`.

---

### Task 1: Metafields data model + extraction module

**Files:**
- Modify: `services/api/src/api/models.py` (`Document` class, ~line 116, after
  `classification_confidence`)
- Create: `services/api/alembic/versions/7c966d7eebf4_add_metafields_to_documents.py`
- Create: `services/api/src/api/document_metafields.py`
- Test: `services/api/tests/test_document_metafields.py`

**Interfaces:**
- Produces: `DOC_TYPE_METAFIELD_SCHEMA: dict[str, list[tuple[str, str]]]`,
  `extract_metafields(*, doc_type: str, text: str, user_id: UUID) -> dict`,
  `extract_and_persist_metafields(db, *, document_id: UUID, doc_type: str, text: str, user_id: UUID) -> Document | None`,
  `is_date_field(doc_type: str, field_key: str) -> bool` — all consumed by Task 2
  (event wiring) and Task 3 (ics endpoint).
- Consumes: `api.ai_gateway.chat_completion` (existing), `api.models.Document`
  (existing).

- [ ] **Step 1: Write the failing tests**

Create `services/api/tests/test_document_metafields.py`:

```python
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.db import async_session
from api.document_metafields import extract_and_persist_metafields, extract_metafields, is_date_field
from api.models import Document, User

FAKE_INVOICE_METAFIELDS = '{"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123"}'


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_document(owner_id, doc_type: str | None = "invoice") -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="invoice.pdf", filename="invoice.pdf", mime_type="application/pdf",
            status="ready", ocr_text="Invoice #INV-123, total EUR 500.00, due 2026-08-15.", doc_type=doc_type,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def test_extract_metafields_returns_parsed_output_for_known_doc_type():
    user = await _create_user(_unique("metafielduser"))
    with patch("api.document_metafields.chat_completion", AsyncMock(return_value=FAKE_INVOICE_METAFIELDS)):
        result = await extract_metafields(doc_type="invoice", text="Invoice #INV-123.", user_id=user.id)

    assert result == {"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123"}


async def test_extract_metafields_returns_empty_dict_for_doc_type_with_no_schema():
    user = await _create_user(_unique("metafieldnoschemauser"))
    mock = AsyncMock(return_value=FAKE_INVOICE_METAFIELDS)
    with patch("api.document_metafields.chat_completion", mock):
        result = await extract_metafields(doc_type="other", text="whatever", user_id=user.id)

    assert result == {}
    mock.assert_not_called()


async def test_extract_metafields_returns_empty_dict_on_unparseable_output():
    user = await _create_user(_unique("metafieldbaduser"))
    with patch("api.document_metafields.chat_completion", AsyncMock(return_value="not json at all")):
        result = await extract_metafields(doc_type="invoice", text="whatever", user_id=user.id)

    assert result == {}


async def test_extract_metafields_drops_keys_not_in_the_declared_schema():
    user = await _create_user(_unique("metafieldextrauser"))
    fake = '{"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123", "made_up_field": "x"}'
    with patch("api.document_metafields.chat_completion", AsyncMock(return_value=fake)):
        result = await extract_metafields(doc_type="invoice", text="whatever", user_id=user.id)

    assert "made_up_field" not in result


async def test_extract_metafields_requests_the_json_schema_not_bare_json_mode():
    user = await _create_user(_unique("metafieldschemauser"))
    mock = AsyncMock(return_value=FAKE_INVOICE_METAFIELDS)
    with patch("api.document_metafields.chat_completion", mock):
        await extract_metafields(doc_type="invoice", text="whatever", user_id=user.id)

    schema = mock.call_args.kwargs["schema"]
    assert set(schema["properties"]) == {"amount", "due_date", "invoice_number"}


async def test_extract_and_persist_metafields_updates_document():
    user = await _create_user(_unique("metafieldpersistuser"))
    document = await _create_document(user.id, doc_type="invoice")

    with patch("api.document_metafields.chat_completion", AsyncMock(return_value=FAKE_INVOICE_METAFIELDS)):
        async with async_session() as db:
            updated = await extract_and_persist_metafields(
                db, document_id=document.id, doc_type="invoice", text=document.ocr_text, user_id=user.id
            )

    assert updated is not None
    assert updated.metafields == {"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123"}


async def test_extract_and_persist_metafields_leaves_metafields_unset_on_unparseable_output():
    user = await _create_user(_unique("metafieldpersistbaduser"))
    document = await _create_document(user.id, doc_type="invoice")

    with patch("api.document_metafields.chat_completion", AsyncMock(return_value="garbage")):
        async with async_session() as db:
            result = await extract_and_persist_metafields(
                db, document_id=document.id, doc_type="invoice", text=document.ocr_text, user_id=user.id
            )

    assert result is not None
    assert result.metafields is None


async def test_extract_and_persist_metafields_returns_none_for_unknown_document():
    user = await _create_user(_unique("metafieldunknowndocuser"))
    async with async_session() as db:
        result = await extract_and_persist_metafields(
            db, document_id=uuid4(), doc_type="invoice", text="x", user_id=user.id
        )
    assert result is None


def test_is_date_field_identifies_declared_date_fields():
    assert is_date_field("invoice", "due_date") is True
    assert is_date_field("invoice", "amount") is False
    assert is_date_field("invoice", "not_a_real_field") is False
    assert is_date_field("other", "anything") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run (on the server, via the rsync round trip):
`docker compose exec -T api uv run pytest tests/test_document_metafields.py -v`
Expected: FAIL/ERROR — `api.document_metafields` does not exist yet.

- [ ] **Step 3: Add the migration**

Create `services/api/alembic/versions/7c966d7eebf4_add_metafields_to_documents.py`:

```python
"""add metafields to documents

Revision ID: 7c966d7eebf4
Revises: e1a5c9f3b7d2
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "7c966d7eebf4"
down_revision: Union[str, None] = "e1a5c9f3b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("metafields", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "metafields")
```

If `e1a5c9f3b7d2` is no longer the head (check with
`docker compose exec -T api uv run alembic heads`), update `down_revision` to whatever
the actual current head is before proceeding.

- [ ] **Step 4: Add the `metafields` column to the `Document` model**

In `services/api/src/api/models.py`, in the `Document` class, immediately after the
`classification_confidence` line:

```python
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    metafields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

(`JSONB` is already imported at the top of `models.py` — no new import needed.)

- [ ] **Step 5: Implement `document_metafields.py`**

Create `services/api/src/api/document_metafields.py`:

```python
"""Document metafield extraction: per-doc-type structured field extraction
(sub-project 3, metafields + UI redesign). Runs after classification -- needs
doc_type to pick the right field schema -- following the same single
schema-constrained chat_completion pattern as document_classification.py.
"""
import json
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.models import Document

logger = logging.getLogger(__name__)

# (field_name, kind) pairs per doc_type. kind is "string" | "date" -- "date" drives
# the frontend's per-field "add to calendar" affordance without the frontend having
# to string-sniff values. Every date-kind field name ends in "_date" by convention,
# so the frontend can also derive kind from the name alone without a schema fetch.
DOC_TYPE_METAFIELD_SCHEMA: dict[str, list[tuple[str, str]]] = {
    "payslip": [("gross_salary", "string"), ("net_salary", "string"), ("period", "string")],
    "salary": [("gross_salary", "string"), ("net_salary", "string"), ("period", "string")],
    "annual_statement": [("gross_salary", "string"), ("net_salary", "string"), ("period", "string")],
    "tax": [("tax_year", "string"), ("amount_due", "string"), ("filing_deadline_date", "date")],
    "pension": [("monthly_amount", "string"), ("provider", "string")],
    "benefits": [("monthly_amount", "string"), ("provider", "string")],
    "bank_statement": [("account_number", "string"), ("period", "string"), ("closing_balance", "string")],
    "bank": [("account_number", "string"), ("period", "string"), ("closing_balance", "string")],
    "invoice": [("amount", "string"), ("due_date", "date"), ("invoice_number", "string")],
    "guardianship": [("case_number", "string"), ("court", "string"), ("effective_date", "date")],
    "mortgage": [("loan_amount", "string"), ("interest_rate", "string"), ("property_address", "string")],
    "housing": [("monthly_rent", "string"), ("start_date", "date"), ("property_address", "string")],
    "notarial": [("deed_type", "string"), ("execution_date", "date"), ("notary", "string")],
    "vehicle": [("license_plate", "string"), ("make_model", "string"), ("registration_date", "date")],
    "policy": [("policy_number", "string"), ("provider", "string"), ("premium", "string")],
    "insurance": [("policy_number", "string"), ("provider", "string"), ("premium", "string")],
    "medical": [("provider", "string"), ("visit_date", "date")],
    "care": [("provider", "string"), ("visit_date", "date")],
    "contract": [("counterparty", "string"), ("start_date", "date"), ("end_date", "date")],
    "education": [("institution", "string"), ("program", "string"), ("graduation_date", "date")],
    "cv": [("full_name", "string"), ("most_recent_role", "string")],
    "government": [("reference_number", "string"), ("deadline_date", "date")],
    "identity_document": [
        ("document_number", "string"), ("birth_date", "date"), ("nationality", "string"), ("expiry_date", "date"),
    ],
    "correspondence": [("subject", "string"), ("reply_by_date", "date")],
    "legal": [("case_number", "string"), ("court", "string"), ("hearing_date", "date")],
}

METAFIELD_PROMPT = """Extract the following fields from this document, if present. Return \
ONLY a JSON object (no prose, no markdown fences) with exactly these keys: {fields}. Use \
null for any field that isn't clearly present in the document. Format any date-like field \
as YYYY-MM-DD.

Document:
{text}"""


def _schema_for(doc_type: str) -> list[tuple[str, str]]:
    return DOC_TYPE_METAFIELD_SCHEMA.get(doc_type, [])


def _json_schema_for(fields: list[tuple[str, str]]) -> dict:
    return {
        "type": "object",
        "properties": {name: {"type": ["string", "null"]} for name, _ in fields},
        "required": [name for name, _ in fields],
    }


def _parse_metafields(raw: str, fields: list[tuple[str, str]]) -> dict:
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
    except (json.JSONDecodeError, ValueError):
        logger.warning("document_metafields: could not parse output: %r", raw[:500])
        return {}

    allowed_keys = {name for name, _ in fields}
    return {key: str(value)[:500] for key, value in payload.items() if key in allowed_keys and value is not None}


async def extract_metafields(*, doc_type: str, text: str, user_id: UUID) -> dict:
    """Extract structured metafields for `doc_type` via the AI Gateway. Returns {} for
    doc_types with no declared schema, or on unparseable model output (graceful
    degradation, same as classify_document -- a bad extraction call must never crash
    the document pipeline it's a subscriber of)."""
    fields = _schema_for(doc_type)
    if not fields:
        return {}

    prompt = METAFIELD_PROMPT.format(fields=", ".join(name for name, _ in fields), text=text[:8000])
    raw = await chat_completion(
        [{"role": "user", "content": prompt}],
        user_id=user_id,
        endpoint="document.extract_metafields",
        schema=_json_schema_for(fields),
    )
    return _parse_metafields(raw, fields)


async def extract_and_persist_metafields(
    db: AsyncSession, *, document_id: UUID, doc_type: str, text: str, user_id: UUID
) -> Document | None:
    document = await db.get(Document, document_id)
    if document is None:
        return None

    metafields = await extract_metafields(doc_type=doc_type, text=text, user_id=user_id)
    if metafields:
        document.metafields = metafields
        await db.commit()
        await db.refresh(document)
    return document


def is_date_field(doc_type: str, field_key: str) -> bool:
    return any(name == field_key and kind == "date" for name, kind in _schema_for(doc_type))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec -T api uv run pytest tests/test_document_metafields.py -v`
Expected: PASS (10 tests).

- [ ] **Step 7: Commit**

```bash
git add services/api/src/api/models.py services/api/src/api/document_metafields.py \
  services/api/alembic/versions/7c966d7eebf4_add_metafields_to_documents.py \
  services/api/tests/test_document_metafields.py
git commit -m "feat: add document metafields extraction module + Document.metafields column"
```

---

### Task 2: Event wiring + settings flag + API exposure

**Files:**
- Modify: `services/api/src/api/config.py` (add `auto_extract_metafields_on_ready`)
- Modify: `services/api/src/api/documents.py` (import, event handler,
  `DocumentDetailOut.metafields`, `get_document` endpoint)
- Test: `services/api/tests/test_document_metafields_events.py`

**Interfaces:**
- Consumes: `extract_and_persist_metafields` from Task 1;
  `EventType.DOCUMENT_CLASSIFIED` (existing, published by `_handle_classify_document`
  in `documents.py` with payload `{"document_id": ..., "doc_type": ...}`).
- Produces: `DocumentDetailOut.metafields: dict | None`, included in the
  `GET /documents/{document_id}` response — consumed by Task 4/5 (frontend).

- [ ] **Step 1: Write the failing tests**

Create `services/api/tests/test_document_metafields_events.py`:

```python
from unittest.mock import AsyncMock, patch

from api.ldap_auth import LdapIdentity

FAKE_EMBEDDING = [0.1] * 768
FAKE_CLASSIFICATION = (
    '{"doc_type": "invoice", "tags": ["btw"], "confidence": 0.9, '
    '"correspondent": {"name": "Acme BV", "street": null, "house_number": null, '
    '"po_box": null, "postal_code": null, "city": null, "country": null}}'
)
FAKE_OTHER_CLASSIFICATION = (
    '{"doc_type": "other", "tags": [], "confidence": 0.3, '
    '"correspondent": {"name": null, "street": null, "house_number": null, '
    '"po_box": null, "postal_code": null, "city": null, "country": null}}'
)
FAKE_METAFIELDS = '{"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123"}'


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_metafields_extracted_after_classification(client):
    token = await _login(client, "metafieldeventuser1")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value="Invoice #INV-123, total EUR 500.00, due 2026-08-15."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
        patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_CLASSIFICATION)),
        patch("api.document_metafields.chat_completion", AsyncMock(return_value=FAKE_METAFIELDS)),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("invoice.txt", b"invoice text", "text/plain")}
        )
        document_id = upload.json()["id"]

    detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["doc_type"] == "invoice"
    assert body["metafields"] == {"amount": "500.00", "due_date": "2026-08-15", "invoice_number": "INV-123"}


async def test_metafields_skipped_when_auto_extract_metafields_disabled(client):
    token = await _login(client, "metafieldeventuser2")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value="Invoice #INV-123, total EUR 500.00."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
        patch("api.documents.settings.auto_extract_metafields_on_ready", False),
        patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_CLASSIFICATION)),
        patch("api.document_metafields.chat_completion", AsyncMock(return_value=FAKE_METAFIELDS)) as mock_call,
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("invoice2.txt", b"invoice text", "text/plain")}
        )
        document_id = upload.json()["id"]

    detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert detail.json()["metafields"] is None
    mock_call.assert_not_called()


async def test_metafields_not_extracted_when_doc_type_has_no_schema(client):
    token = await _login(client, "metafieldeventuser3")
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value="Some unclassifiable text."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.documents.settings.auto_extract_vehicles_on_ready", False),
        patch("api.documents.settings.auto_extract_facts_on_ready", False),
        patch("api.document_classification.chat_completion", AsyncMock(return_value=FAKE_OTHER_CLASSIFICATION)),
        patch("api.document_metafields.chat_completion", AsyncMock(return_value=FAKE_METAFIELDS)) as mock_call,
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("other.txt", b"other text", "text/plain")}
        )
        document_id = upload.json()["id"]

    detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert detail.json()["metafields"] is None
    mock_call.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api uv run pytest tests/test_document_metafields_events.py -v`
Expected: FAIL — `metafields` key missing from the `GET /documents/{id}` response
(`DocumentDetailOut` has no such field yet), and no handler is subscribed to
`DOCUMENT_CLASSIFIED` yet.

- [ ] **Step 3: Add the settings flag**

In `services/api/src/api/config.py`, immediately after `auto_extract_facts_on_ready`:

```python
    auto_extract_facts_on_ready: bool = True
    auto_extract_metafields_on_ready: bool = True
```

- [ ] **Step 4: Wire the event handler and API field**

In `services/api/src/api/documents.py`:

Add to the import block (alphabetically, after the `document_classification` import):

```python
from api.document_classification import classify_and_persist
from api.document_metafields import extract_and_persist_metafields
```

Add `metafields` to `DocumentDetailOut` (after `correspondent_country`):

```python
class DocumentDetailOut(DocumentOut):
    ocr_text: str | None
    chunk_count: int
    summary: str | None
    correspondent_street: str | None
    correspondent_house_number: str | None
    correspondent_po_box: str | None
    correspondent_postal_code: str | None
    correspondent_city: str | None
    correspondent_country: str | None
    metafields: dict | None
```

Add the event handler, immediately after `_handle_classify_document`:

```python
@subscribe(EventType.DOCUMENT_CLASSIFIED)
async def _handle_extract_metafields(event: Event) -> None:
    if not settings.auto_extract_metafields_on_ready:
        return
    document_id = event.payload["document_id"]
    doc_type = event.payload["doc_type"]
    async with async_session() as db:
        document = await db.get(Document, document_id)
        if document is None or not document.ocr_text:
            return
        await extract_and_persist_metafields(
            db, document_id=document_id, doc_type=doc_type, text=document.ocr_text, user_id=document.owner_id
        )
```

Add `metafields=document.metafields` to the `DocumentDetailOut(...)` construction in
`get_document` (after `correspondent_country=document.correspondent_country,`):

```python
        correspondent_country=document.correspondent_country,
        metafields=document.metafields,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T api uv run pytest tests/test_document_metafields_events.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the full backend regression suite**

Run: `docker compose exec -T api uv run pytest -v`
Expected: PASS, same count as before this task plus the new tests (no regressions).

- [ ] **Step 7: Commit**

```bash
git add services/api/src/api/config.py services/api/src/api/documents.py \
  services/api/tests/test_document_metafields_events.py
git commit -m "feat: auto-extract document metafields after classification"
```

---

### Task 3: Metafield `.ics` export endpoint

**Files:**
- Modify: `services/api/src/api/documents.py` (new route, new imports)
- Test: `services/api/tests/test_document_metafields_ics.py`

**Interfaces:**
- Consumes: `is_date_field` (Task 1), `_can_read_document` (existing, `documents.py`),
  `build_vevent_calendar`/`format_ics_date`/`ics_slug` (existing, `api.ics_utils`).
- Produces: `GET /documents/{document_id}/metafields/{field_key}/ics` — consumed by
  Task 4 (frontend `downloadMetafieldIcs`).

- [ ] **Step 1: Write the failing tests**

Create `services/api/tests/test_document_metafields_ics.py`:

```python
"""Metafield .ics export -- lets a user download a calendar event for any
date-typed extracted metafield (e.g. an invoice's due_date), without requiring
the full calendar-sync sub-project. Documents are created directly via the ORM
with metafields already set, same rationale as test_document_access_control.py:
the upload pipeline's LLM calls aren't relevant here.
"""
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Document, User


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_id(username: str) -> UUID:
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one().id


async def _create_document(owner_id: UUID, title: str, *, doc_type: str | None, metafields: dict | None) -> UUID:
    document_id = uuid4()
    async with async_session() as db:
        db.add(
            Document(
                id=document_id, owner_id=owner_id, title=title, filename=f"{title}.txt",
                mime_type="text/plain", status="ready", doc_type=doc_type, metafields=metafields,
            )
        )
        await db.commit()
    return document_id


async def test_export_metafield_ics_returns_well_formed_all_day_vevent(client):
    token = await _login(client, "icsmetauser1")
    headers = {"Authorization": f"Bearer {token}"}
    owner_id = await _user_id("icsmetauser1")
    document_id = await _create_document(
        owner_id, "Electric bill", doc_type="invoice",
        metafields={"amount": "120.00", "due_date": "2026-08-01", "invoice_number": "INV-9"},
    )

    response = await client.get(f"/documents/{document_id}/metafields/due_date/ics", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    body = response.text
    assert "BEGIN:VEVENT" in body
    assert "DTSTART;VALUE=DATE:20260801" in body


async def test_export_metafield_ics_rejects_non_date_field(client):
    token = await _login(client, "icsmetauser2")
    headers = {"Authorization": f"Bearer {token}"}
    owner_id = await _user_id("icsmetauser2")
    document_id = await _create_document(
        owner_id, "Electric bill", doc_type="invoice",
        metafields={"amount": "120.00", "due_date": "2026-08-01", "invoice_number": "INV-9"},
    )

    response = await client.get(f"/documents/{document_id}/metafields/amount/ics", headers=headers)
    assert response.status_code == 409


async def test_export_metafield_ics_rejects_field_with_no_value(client):
    token = await _login(client, "icsmetauser3")
    headers = {"Authorization": f"Bearer {token}"}
    owner_id = await _user_id("icsmetauser3")
    document_id = await _create_document(owner_id, "Electric bill", doc_type="invoice", metafields={})

    response = await client.get(f"/documents/{document_id}/metafields/due_date/ics", headers=headers)
    assert response.status_code == 409


async def test_export_metafield_ics_rejects_unknown_document(client):
    token = await _login(client, "icsmetauser4")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        "/documents/00000000-0000-0000-0000-000000000000/metafields/due_date/ics", headers=headers
    )
    assert response.status_code == 404


async def test_export_metafield_ics_rejects_non_owner(client):
    owner_token = await _login(client, "icsmetaowner1")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    owner_id = await _user_id("icsmetaowner1")
    document_id = await _create_document(
        owner_id, "Private invoice", doc_type="invoice", metafields={"due_date": "2026-08-01"},
    )

    outsider_token = await _login(client, "icsmetaoutsider1")
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    response = await client.get(f"/documents/{document_id}/metafields/due_date/ics", headers=outsider_headers)
    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api uv run pytest tests/test_document_metafields_ics.py -v`
Expected: FAIL — 404 for all requests, route doesn't exist yet.

- [ ] **Step 3: Implement the endpoint**

In `services/api/src/api/documents.py`:

Change the `datetime` import at the top to also import `date`:

```python
from datetime import date, datetime, timezone
```

Task 2 already added `from api.document_metafields import extract_and_persist_metafields`
to this file — extend that same line to also import `is_date_field`:

```python
from api.document_metafields import extract_and_persist_metafields, is_date_field
```

Add a new import line for the ics helpers:

```python
from api.ics_utils import build_vevent_calendar, format_ics_date, ics_slug
```

Add the route, immediately after `get_document` (before `get_document_file`):

```python
@router.get("/{document_id}/metafields/{field_key}/ics")
async def export_metafield_ics(
    document_id: UUID,
    field_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> Response:
    """All-day VEVENT built from a single extracted metafield's date value.
    Stateless, like tasks.py's export_task_ics -- no Appointment row is created;
    full document-to-calendar auto-sync is a separate, later sub-project."""
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not await _can_read_document(db, document, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this document")
    if document.doc_type is None or not is_date_field(document.doc_type, field_key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Field is not a date field for this document's type"
        )
    raw_value = (document.metafields or {}).get(field_key)
    if not raw_value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Field has no value to export")
    try:
        parsed_date = date.fromisoformat(raw_value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Field value is not a valid date")

    ics_text = build_vevent_calendar(
        uid=f"{document.id}-{field_key}",
        summary=f"{document.title}: {field_key.replace('_', ' ').title()}",
        dtstart=format_ics_date(parsed_date),
        all_day=True,
        prodid="-//CollaBrains//Documents//EN",
    )
    slug = ics_slug(f"{document.title}-{field_key}")
    return Response(
        content=ics_text,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{slug}.ics"'},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api uv run pytest tests/test_document_metafields_ics.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full backend regression suite**

Run: `docker compose exec -T api uv run pytest -v`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/documents.py services/api/tests/test_document_metafields_ics.py
git commit -m "feat: add per-metafield .ics export endpoint"
```

---

### Task 4: Frontend API client — metafields + ics download

**Files:**
- Modify: `apps/web/src/lib/api.ts` (`DocumentDetailOut.metafields`,
  `downloadMetafieldIcs`)
- Modify: `apps/web/src/lib/api.test.ts`

**Interfaces:**
- Consumes: `fetchAndOpenIcs` (existing, `api.ts`, used by `downloadTaskIcs`/
  `downloadAppointmentIcs`).
- Produces: `DocumentDetailOut.metafields: Record<string, string> | null`,
  `downloadMetafieldIcs(documentId: string, fieldKey: string, filename: string): Promise<void>`
  — consumed by Task 5 (`DocumentDetail.tsx`).

- [ ] **Step 1: Write the failing tests**

In `apps/web/src/lib/api.test.ts`, add `downloadMetafieldIcs` to the top import:

```ts
import { ApiError, approveEntity, clearToken, downloadAppointmentIcs, downloadMetafieldIcs, downloadTaskIcs, login, request, setToken } from "./api";
```

Add a new `describe` block, after the existing `describe("downloadAppointmentIcs", ...)`
block:

```ts
describe("downloadMetafieldIcs", () => {
  beforeEach(() => {
    clearToken();
    vi.stubGlobal("fetch", vi.fn());
    URL.createObjectURL = vi.fn(() => "blob:mock-url");
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches the metafield ics endpoint with the auth header and triggers a download", async () => {
    setToken("secret-token");
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response("BEGIN:VCALENDAR", { status: 200 }));
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    vi.useFakeTimers();
    await downloadMetafieldIcs("d1", "due_date", "due-date.ics");

    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/documents/d1/metafields/due_date/ics");
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer secret-token");
    expect(clickSpy).toHaveBeenCalled();

    vi.advanceTimersByTime(10000);
    vi.useRealTimers();
    clickSpy.mockRestore();
  });

  it("throws ApiError on a non-ok response", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response("", { status: 404, statusText: "Not Found" }));

    await expect(downloadMetafieldIcs("missing", "due_date", "x.ics")).rejects.toBeInstanceOf(ApiError);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/lib/api.test.ts`
Expected: FAIL — `downloadMetafieldIcs` is not exported from `./api`.

- [ ] **Step 3: Implement the API client additions**

In `apps/web/src/lib/api.ts`, add `metafields` to `DocumentDetailOut` (after
`correspondent_country`):

```ts
export interface DocumentDetailOut extends DocumentOut {
  ocr_text: string | null;
  chunk_count: number;
  summary: string | null;
  correspondent_street: string | null;
  correspondent_house_number: string | null;
  correspondent_po_box: string | null;
  correspondent_postal_code: string | null;
  correspondent_city: string | null;
  correspondent_country: string | null;
  metafields: Record<string, string> | null;
}
```

Add `downloadMetafieldIcs`, immediately after `downloadAppointmentIcs`:

```ts
export async function downloadMetafieldIcs(documentId: string, fieldKey: string, filename: string): Promise<void> {
  await fetchAndOpenIcs(`/documents/${documentId}/metafields/${fieldKey}/ics`, filename);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/lib/api.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/api.test.ts
git commit -m "feat: add downloadMetafieldIcs and DocumentDetailOut.metafields to the API client"
```

---

### Task 5: `DocumentDetail.tsx` metafields card

**Files:**
- Modify: `apps/web/src/routes/DocumentDetail.tsx`
- Modify: `apps/web/src/routes/DocumentDetail.test.tsx`
- Modify: `apps/web/src/locales/en.json`, `nl.json`, `de.json`

**Interfaces:**
- Consumes: `DocumentDetailOut.metafields`, `downloadMetafieldIcs` (Task 4).

- [ ] **Step 1: Write the failing tests**

In `apps/web/src/routes/DocumentDetail.test.tsx`, add `downloadMetafieldIcs: vi.fn()`
to the `api` mock block, and `metafields: null` to `mockDoc`:

```ts
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getDocument: vi.fn(),
    deleteDocument: vi.fn(),
    summarizeDocument: vi.fn(),
    reprocessDocument: vi.fn(),
    downloadDocumentFile: vi.fn(),
    previewDocumentFile: vi.fn(),
    downloadMetafieldIcs: vi.fn(),
  };
});

const mockDoc = {
  id: "doc-1",
  title: "factuur-77621.pdf",
  filename: "factuur-77621.pdf",
  mime_type: "application/pdf",
  status: "ready",
  error: null,
  doc_type: null,
  tags: [],
  correspondent: null,
  created_at: "2026-07-08T19:11:38Z",
  processed_at: "2026-07-08T19:12:00Z",
  category_id: null,
  ocr_text: "Extracted text here",
  chunk_count: 3,
  summary: null,
  correspondent_street: null,
  correspondent_house_number: null,
  correspondent_po_box: null,
  correspondent_postal_code: null,
  correspondent_city: null,
  correspondent_country: null,
  metafields: null,
};
```

Add new test cases, after the existing tests in the file (inside the same
`describe`/top-level test list):

```tsx
it("renders the metafields card when metafields are present", async () => {
  vi.mocked(api.getDocument).mockResolvedValue({
    ...mockDoc, doc_type: "invoice",
    metafields: { amount: "500.00", due_date: "2026-08-15", invoice_number: "INV-123" },
  });
  renderAt("doc-1");

  expect(await screen.findByText("Invoice Number")).toBeInTheDocument();
  expect(screen.getByText("INV-123")).toBeInTheDocument();
});

it("does not render the metafields card when metafields are absent", async () => {
  vi.mocked(api.getDocument).mockResolvedValue(mockDoc);
  renderAt("doc-1");

  await screen.findByText(mockDoc.title);
  expect(screen.queryByText("Invoice Number")).not.toBeInTheDocument();
});

it("shows an add-to-calendar button for date-like metafields and downloads on click", async () => {
  vi.mocked(api.getDocument).mockResolvedValue({
    ...mockDoc, doc_type: "invoice",
    metafields: { amount: "500.00", due_date: "2026-08-15" },
  });
  vi.mocked(api.downloadMetafieldIcs).mockResolvedValue(undefined);
  renderAt("doc-1");

  const button = await screen.findByRole("button", { name: /add to calendar/i });
  fireEvent.click(button);

  await waitFor(() =>
    expect(api.downloadMetafieldIcs).toHaveBeenCalledWith("doc-1", "due_date", expect.stringContaining("due-date"))
  );
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/routes/DocumentDetail.test.tsx`
Expected: FAIL — no metafields card rendered yet, `downloadMetafieldIcs` not imported.

- [ ] **Step 3: Add i18n keys**

In `apps/web/src/locales/en.json`, in the `documentDetail` object, add two keys
(after `"correspondent"`):

```json
    "correspondent": "Correspondent",
    "metafields": "Details",
    "addToCalendar": "Add to calendar"
```

In `apps/web/src/locales/nl.json`, in the `documentDetail` object, add (matching the
existing Dutch tone of nearby keys):

```json
    "metafields": "Details",
    "addToCalendar": "Aan agenda toevoegen"
```

In `apps/web/src/locales/de.json`, in the `documentDetail` object, add:

```json
    "metafields": "Details",
    "addToCalendar": "Zum Kalender hinzufügen"
```

- [ ] **Step 4: Implement the metafields card**

In `apps/web/src/routes/DocumentDetail.tsx`, add `downloadMetafieldIcs` to the
existing `../lib/api` import list:

```tsx
import {
  ApiError,
  deleteDocument,
  downloadDocumentFile,
  downloadMetafieldIcs,
  getDocument,
  previewDocumentFile,
  reprocessDocument,
  summarizeDocument,
  type DocumentDetailOut,
} from "../lib/api";
```

Add two helper functions, after `formatCorrespondentAddress`:

```tsx
function humanizeFieldKey(key: string): string {
  return key
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function isDateLikeKey(key: string): boolean {
  return key.endsWith("_date");
}
```

Add a handler function inside the `DocumentDetail` component, after `handlePreview`:

```tsx
  async function handleDownloadMetafieldIcs(fieldKey: string) {
    if (!id) return;
    const slug = `${doc?.title ?? "document"}-${fieldKey}`
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
    try {
      await downloadMetafieldIcs(id, fieldKey, `${slug || "event"}.ics`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("documentDetail.downloadError"));
    }
  }
```

Add the metafields card in the JSX, after the existing "Classification" card (i.e.
right after its closing `)}` , before the `{doc.summary && (...)}` block):

```tsx
      {doc.metafields && Object.keys(doc.metafields).length > 0 && (
        <Card>
          <h2 className="text-sm font-medium text-ink-2">{t("documentDetail.metafields")}</h2>
          <div className="mt-2 flex flex-col gap-2">
            {Object.entries(doc.metafields).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between gap-2 text-sm">
                <span className="text-ink-3">{humanizeFieldKey(key)}</span>
                <div className="flex items-center gap-2">
                  <span className="text-ink">{value}</span>
                  {isDateLikeKey(key) && (
                    <Button variant="ghost" size="sm" onClick={() => handleDownloadMetafieldIcs(key)}>
                      {t("documentDetail.addToCalendar")}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run src/routes/DocumentDetail.test.tsx`
Expected: PASS.

- [ ] **Step 6: Run the full frontend test suite and build**

Run: `npx vitest run` then `npx vite build`
Expected: all tests PASS, build succeeds with no new errors.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/routes/DocumentDetail.tsx apps/web/src/routes/DocumentDetail.test.tsx \
  apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat: render document metafields with per-field calendar export"
```

---

### Task 6: Grouped category filter in the document list

**Files:**
- Create: `apps/web/src/components/CategoryFilterGrid.tsx`
- Create: `apps/web/src/components/CategoryFilterGrid.test.tsx`
- Modify: `apps/web/src/routes/Workspace.tsx`
- Modify: `apps/web/src/routes/Workspace.test.tsx`

**Interfaces:**
- Consumes: `CategoryOut` (existing, `api.ts`), design tokens from sub-project 1
  (`glass-surface`, `bg-gradient-brand`, `rounded-ds-*`).
- Produces: `CategoryFilterGrid` component, consumed by `Workspace.tsx`.

- [ ] **Step 1: Write the failing component test**

Create `apps/web/src/components/CategoryFilterGrid.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CategoryFilterGrid } from "./CategoryFilterGrid";
import type { CategoryOut } from "../lib/api";

const categories: CategoryOut[] = [
  { id: "parent-finance", slug: "finance", icon: "Coins", color: "#FF9500", parent_id: null },
  { id: "cat-payslip", slug: "payslip", icon: "Banknote", color: "#FF9500", parent_id: "parent-finance" },
  { id: "cat-invoice", slug: "invoice", icon: "Receipt", color: "#FF3B30", parent_id: "parent-finance" },
  { id: "parent-other", slug: "other_group", icon: "Inbox", color: "#8E8E93", parent_id: null },
  { id: "cat-other-docs", slug: "other_documents", icon: "File", color: "#8E8E93", parent_id: "parent-other" },
];

describe("CategoryFilterGrid", () => {
  it("renders a group header per parent category and a chip per child", () => {
    render(
      <CategoryFilterGrid categories={categories} activeIds={new Set()} onToggleGroup={() => {}} onToggleChild={() => {}} />
    );

    expect(screen.getByRole("button", { name: /finance/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Payslip & Salary" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Invoices" })).toBeInTheDocument();
  });

  it("calls onToggleChild with the child's id when a child chip is clicked", () => {
    const onToggleChild = vi.fn();
    render(
      <CategoryFilterGrid categories={categories} activeIds={new Set()} onToggleGroup={() => {}} onToggleChild={onToggleChild} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Payslip & Salary" }));
    expect(onToggleChild).toHaveBeenCalledWith("cat-payslip");
  });

  it("calls onToggleGroup with all child ids when a group header is clicked", () => {
    const onToggleGroup = vi.fn();
    render(
      <CategoryFilterGrid categories={categories} activeIds={new Set()} onToggleGroup={onToggleGroup} onToggleChild={() => {}} />
    );

    fireEvent.click(screen.getByRole("button", { name: /finance/i }));
    expect(onToggleGroup).toHaveBeenCalledWith(["cat-payslip", "cat-invoice"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/CategoryFilterGrid.test.tsx`
Expected: FAIL — `./CategoryFilterGrid` does not exist yet.

- [ ] **Step 3: Implement `CategoryFilterGrid.tsx`**

Create `apps/web/src/components/CategoryFilterGrid.tsx`:

```tsx
import { Briefcase, Coins, Home, Inbox, Shield, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { CategoryOut } from "../lib/api";

const PARENT_CATEGORY_ICON: Record<string, LucideIcon> = {
  finance: Coins,
  housing_vehicle: Home,
  insurance_care: Shield,
  work_education: Briefcase,
  government_identity: Shield,
  other_group: Inbox,
};

interface CategoryFilterGridProps {
  categories: CategoryOut[];
  activeIds: Set<string>;
  onToggleGroup: (childIds: string[]) => void;
  onToggleChild: (id: string) => void;
}

export function CategoryFilterGrid({ categories, activeIds, onToggleGroup, onToggleChild }: CategoryFilterGridProps) {
  const { t } = useTranslation();
  const parents = categories.filter((c) => c.parent_id === null);

  return (
    <div className="flex flex-wrap gap-3">
      {parents.map((parent) => {
        const children = categories.filter((c) => c.parent_id === parent.id);
        const childIds = children.map((c) => c.id);
        const groupActive = childIds.length > 0 && childIds.every((id) => activeIds.has(id));
        const Icon = PARENT_CATEGORY_ICON[parent.slug] ?? Inbox;

        return (
          <div key={parent.id} className="glass-surface flex min-w-[220px] flex-col gap-2 rounded-ds-lg p-3">
            <button
              type="button"
              onClick={() => onToggleGroup(childIds)}
              disabled={childIds.length === 0}
              className={`flex items-center gap-2 rounded-ds-md px-2 py-1 text-left text-sm font-medium transition-colors ${
                groupActive ? "bg-gradient-brand text-white" : "text-ink hover:bg-surface"
              }`}
            >
              <Icon size={16} />
              {t(`categories.${parent.slug}`)}
            </button>
            {children.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {children.map((child) => (
                  <button
                    key={child.id}
                    type="button"
                    onClick={() => onToggleChild(child.id)}
                    className={`rounded-ds-sm border px-2 py-0.5 text-xs transition-colors ${
                      activeIds.has(child.id)
                        ? "border-accent bg-accent/10 text-accent"
                        : "border-edge text-ink-2 hover:border-accent"
                    }`}
                  >
                    {t(`categories.${child.slug}`)}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/CategoryFilterGrid.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Update `Workspace.tsx`'s existing category-filter tests**

The two existing category-filter tests in `apps/web/src/routes/Workspace.test.tsx`
use flat, childless mock categories against the old `FilterChips`-based UI being
replaced in this task — they must be rewritten against the new grouped UI (not just
supplemented), using realistic parent+child fixtures. Replace both tests (currently
titled `"shows a category filter chip and toggling it narrows the table to matching
documents"` and `"removing an active category filter chip restores the full
table"`):

```tsx
  it("toggling a child category chip narrows the table to matching documents", async () => {
    vi.mocked(api.listCategories).mockResolvedValue([
      { id: "parent-finance", slug: "finance", icon: "Coins", color: "#FF9500", parent_id: null },
      { id: "cat-1", slug: "payslip", icon: "Banknote", color: "#FF9500", parent_id: "parent-finance" },
      { id: "cat-2", slug: "invoice", icon: "Receipt", color: "#FF3B30", parent_id: "parent-finance" },
    ]);
    vi.mocked(api.listDocuments).mockResolvedValue([
      { ...docs[0], category_id: "cat-1" },
      { ...docs[1], category_id: "cat-2" },
    ]);
    renderPage();
    await screen.findByText("document-0.pdf");

    fireEvent.click(await screen.findByRole("button", { name: "Payslip & Salary" }));

    expect(screen.getByText("document-0.pdf")).toBeInTheDocument();
    expect(screen.queryByText("document-1.pdf")).not.toBeInTheDocument();
  });

  it("toggling a category group header filters to all its children at once", async () => {
    vi.mocked(api.listCategories).mockResolvedValue([
      { id: "parent-finance", slug: "finance", icon: "Coins", color: "#FF9500", parent_id: null },
      { id: "cat-1", slug: "payslip", icon: "Banknote", color: "#FF9500", parent_id: "parent-finance" },
      { id: "cat-2", slug: "invoice", icon: "Receipt", color: "#FF3B30", parent_id: "parent-finance" },
    ]);
    vi.mocked(api.listDocuments).mockResolvedValue([
      { ...docs[0], category_id: "cat-1" },
      { ...docs[1], category_id: "cat-2" },
      { ...docs[2], category_id: null },
    ]);
    renderPage();
    await screen.findByText("document-0.pdf");

    fireEvent.click(await screen.findByRole("button", { name: "Finance" }));

    expect(screen.getByText("document-0.pdf")).toBeInTheDocument();
    expect(screen.getByText("document-1.pdf")).toBeInTheDocument();
    expect(screen.queryByText("document-2.pdf")).not.toBeInTheDocument();
  });
```

- [ ] **Step 6: Run the updated Workspace tests to verify they fail**

Run: `npx vitest run src/routes/Workspace.test.tsx`
Expected: FAIL — `Workspace.tsx` still renders the old flat `FilterChips` UI for
categories, so no button with name `"Payslip & Salary"`/`"Finance"` exists yet.

- [ ] **Step 7: Wire `CategoryFilterGrid` into `Workspace.tsx`**

Replace the `import { FilterChips } from "../components/ui/FilterChips";` line's
neighbor imports by adding:

```tsx
import { CategoryFilterGrid } from "../components/CategoryFilterGrid";
```

Remove the now-unused `CATEGORY_FILTER_OPTIONS` line:

```tsx
  const CATEGORY_FILTER_OPTIONS = categories.map((c) => ({ id: c.id, label: t(`categories.${c.slug}`) }));
```

Replace the category `FilterChips` block:

```tsx
          {categories.length > 0 && (
            <FilterChips
              label={t("documents.categoryFilterLabel")}
              chips={CATEGORY_FILTER_OPTIONS.filter((opt) => categoryFilters.includes(opt.id))}
              onRemove={(id) => setCategoryFilters((prev) => prev.filter((c) => c !== id))}
              addOptions={CATEGORY_FILTER_OPTIONS.filter((opt) => !categoryFilters.includes(opt.id))}
              onAdd={(opt) => setCategoryFilters((prev) => [...prev, opt.id])}
            />
          )}
```

with:

```tsx
          {categories.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium text-ink-3">{t("documents.categoryFilterLabel")}</p>
              <CategoryFilterGrid
                categories={categories}
                activeIds={activeCategoryFilters}
                onToggleGroup={(childIds) => {
                  const allActive = childIds.every((id) => activeCategoryFilters.has(id));
                  setCategoryFilters((prev) =>
                    allActive
                      ? prev.filter((id) => !childIds.includes(id))
                      : [...new Set([...prev, ...childIds])]
                  );
                }}
                onToggleChild={(id) =>
                  setCategoryFilters((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]))
                }
              />
            </div>
          )}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `npx vitest run src/routes/Workspace.test.tsx`
Expected: PASS.

- [ ] **Step 9: Run the full frontend test suite and build**

Run: `npx vitest run` then `npx vite build`
Expected: all tests PASS, build succeeds with no new errors.

- [ ] **Step 10: Commit**

```bash
git add apps/web/src/components/CategoryFilterGrid.tsx apps/web/src/components/CategoryFilterGrid.test.tsx \
  apps/web/src/routes/Workspace.tsx apps/web/src/routes/Workspace.test.tsx
git commit -m "feat: replace flat category filter chips with a grouped parent/child filter grid"
```

---

## Deployment

After all 6 tasks are complete and committed:

1. Push to `main` (this project commits directly to `main`, no PR flow).
2. On the server (`root@178.254.22.178`, repo at `/opt/collabrains`): `git pull`.
3. Backend deploys automatically via uvicorn `--reload` — no manual step.
4. Run the migration: `docker compose exec -T api uv run alembic upgrade head`.
5. Rebuild the frontend explicitly:
   `docker compose exec web sh -c 'cd /app/apps/web && npx vite build'`
   (`docker compose up -d web` alone does not rebuild it).
6. Verify: upload a test invoice-like document, confirm `doc_type`/`metafields`
   populate on `GET /documents/{id}`, and check the document detail page in the
   browser for the new "Details" card and grouped category filter on `/documents`.
