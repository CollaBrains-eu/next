# LDAP-Style Relational Contact Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Give person/organization entities structured, relational contact fields (phone, PO box address, visiting/establishment address, and per-relationship job title) extracted automatically from documents.

**Architecture:** Same split-recognition-from-parsing pattern as the just-completed address work: the LLM flags candidate phone/PO-box/visiting-address/title text next to an entity, a new deterministic `contact_parser.py` validates/normalizes it, and PO box / visiting address become their own deduped `address` entities via the address machinery that already exists.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pytest/pytest-asyncio, React/TypeScript, Vite.

## Global Constraints

- One `ContactDetail` row per entity (1:1, same pattern as `AddressDetail`) — no multiple-phone-numbers support (YAGNI per spec).
- Gap-fill only: an already-populated `ContactDetail` field is never overwritten by a later extraction.
- No `country` field on `ContactDetail` — country is read from the visiting address's `AddressDetail.country`.
- `EntityRelationship.title` needs no merge logic — relationship rows are already append-only evidence (one new row per document scan).
- No syncing into the OpenLDAP directory service (`ldap_auth.py`) — out of scope, unrelated system.
- Alembic migration must chain from the current head: `a1b2c3d4e5f6` (verified live via `psql` against production, matching this project's established practice of confirming DB state before writing migrations).

---

### Task 1: `contact_parser.py` — deterministic phone/title validation

**Files:**
- Create: `services/api/src/api/contact_parser.py`
- Test: `services/api/tests/test_contact_parser.py`

**Interfaces:**
- Produces: `parse_phone(raw_text: str) -> str | None`, `looks_like_garbage_title(text: str) -> bool` — both used by Task 3.

- [x] **Step 1: Write the failing tests**

```python
# services/api/tests/test_contact_parser.py
from api.contact_parser import looks_like_garbage_title, parse_phone


def test_parse_phone_normalizes_dutch_landline():
    assert parse_phone("tel. 010-1234567") == "010-1234567"


def test_parse_phone_normalizes_international_format():
    assert parse_phone("Phone: +31 6 12345678") == "+31 6 12345678"


def test_parse_phone_rejects_too_few_digits():
    assert parse_phone("kamer 12") is None


def test_parse_phone_rejects_email_snippet():
    assert parse_phone("info@acme-corp-2026.com") is None


def test_parse_phone_returns_none_for_empty_string():
    assert parse_phone("") is None


def test_looks_like_garbage_title_rejects_email():
    assert looks_like_garbage_title("info@acme.com") is True


def test_looks_like_garbage_title_rejects_url():
    assert looks_like_garbage_title("https://acme.com") is True


def test_looks_like_garbage_title_rejects_overly_long_text():
    assert looks_like_garbage_title("x" * 150) is True


def test_looks_like_garbage_title_accepts_normal_title():
    assert looks_like_garbage_title("Directeur") is False


def test_looks_like_garbage_title_rejects_empty_string():
    assert looks_like_garbage_title("") is True
```

- [x] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api pytest tests/test_contact_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'api.contact_parser'`

- [x] **Step 3: Write the implementation**

```python
# services/api/src/api/contact_parser.py
"""Deterministic contact-field validation (phone normalization, title guardrail).

Same split as address_parser.py: entity_agent.py's LLM call identifies "this text
near entity Y looks like a phone number / job title", this module validates and
normalizes it rather than trusting the LLM to format it correctly -- see
docs/superpowers/specs/2026-07-23-ldap-contact-details-design.md.
"""
import re

_PHONE_CHARS_RE = re.compile(r"[\d\s\-\+\(\)]{6,20}")
_PHONE_MIN_DIGITS = 7

_GARBAGE_TITLE_RE = re.compile(r"@|https?://|www\.", re.IGNORECASE)
_TITLE_MAX_LENGTH = 100


def parse_phone(raw_text: str) -> str | None:
    """Normalize a candidate phone snippet to a cleaned digits-and-symbols
    string, or None if it doesn't look like a phone number. Never guesses a
    country code or reformats into E.164 -- just strips surrounding noise and
    validates there are enough digits to plausibly be a phone number."""
    text = raw_text.strip()
    if not text or "@" in text or "http" in text.lower():
        return None
    match = _PHONE_CHARS_RE.search(text)
    if not match:
        return None
    candidate = match.group(0).strip()
    if sum(c.isdigit() for c in candidate) < _PHONE_MIN_DIGITS:
        return None
    return re.sub(r"\s{2,}", " ", candidate)


def looks_like_garbage_title(text: str) -> bool:
    """Reject title candidates that are too long or contain an email/URL --
    same guardrail pattern as entity_agent.py's _looks_like_garbage_address
    (an LLM occasionally mis-slots the wrong field's text into this one)."""
    stripped = text.strip()
    if not stripped or len(stripped) > _TITLE_MAX_LENGTH:
        return True
    return bool(_GARBAGE_TITLE_RE.search(stripped))
```

- [x] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api pytest tests/test_contact_parser.py -v`
Expected: PASS (all 10 tests). If `test_parse_phone_normalizes_international_format` fails because of a stray leading character, adjust the regex/strip logic (not the test) — the contract is "clean, human-readable phone text," not exact byte-for-byte preservation.

- [x] **Step 5: Commit**

```bash
git add services/api/src/api/contact_parser.py services/api/tests/test_contact_parser.py
git commit -m "feat: add deterministic phone/title parsing for contact details"
```

---

### Task 2: Schema — `ContactDetail` model, `EntityRelationship.title`, migration

**Files:**
- Modify: `services/api/src/api/models.py` (after `AddressDetail`, ~line 382)
- Modify: `services/api/src/api/models.py` (`EntityRelationship`, ~line 331)
- Create: `services/api/alembic/versions/5dd392e03c44_contact_details.py`

**Interfaces:**
- Consumes: none (pure schema task).
- Produces: `ContactDetail(entity_id, phone, po_box_address_entity_id, visiting_address_entity_id)`, `EntityRelationship.title: str | None` — used by Task 3 and Task 4.

- [x] **Step 1: Add `ContactDetail` model and `EntityRelationship.title`**

In `services/api/src/api/models.py`, add `title` to `EntityRelationship`:

```python
class EntityRelationship(Base):
    """A directed, typed relationship between two entities, evidenced by a document."""

    __tablename__ = "entity_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Add `ContactDetail` directly after `AddressDetail` (~line 382, before `class Residency`):

```python
class ContactDetail(Base):
    """Structured contact fields for an Entity where entity_type is 'person' or
    'organization'. One row per entity (same 1:1 pattern as AddressDetail) --
    gap-filled across documents, never fragmented into duplicates. PO box and
    visiting address are FKs to `entities.id` (type 'address'), not raw text,
    reusing the same parsing/dedup/maps_url machinery AddressDetail already has.
    """

    __tablename__ = "contact_details"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    po_box_address_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    visiting_address_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
```

- [x] **Step 2: Write the migration**

```python
# services/api/alembic/versions/5dd392e03c44_contact_details.py
"""contact details

Revision ID: 5dd392e03c44
Revises: a1b2c3d4e5f6
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "5dd392e03c44"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_details",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("po_box_address_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("visiting_address_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["po_box_address_entity_id"], ["entities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["visiting_address_entity_id"], ["entities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("entity_id"),
    )
    op.add_column("entity_relationships", sa.Column("title", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("entity_relationships", "title")
    op.drop_table("contact_details")
```

- [x] **Step 3: Apply the migration and verify**

Run: `docker compose exec api alembic upgrade head`
Expected: migration `5dd392e03c44` applies cleanly.

Run: `docker compose exec -T postgres psql -U collabrains -d collabrains -c '\d contact_details'`
Expected: table exists with the four expected columns and FKs.

- [x] **Step 4: Commit**

```bash
git add services/api/src/api/models.py services/api/alembic/versions/5dd392e03c44_contact_details.py
git commit -m "feat: add ContactDetail table and EntityRelationship.title column"
```

---

### Task 3: Extraction pipeline — `entity_agent.py`

**Files:**
- Modify: `services/api/src/api/entity_agent.py`
- Test: `services/api/tests/test_entities.py`

**Interfaces:**
- Consumes: `parse_phone`, `looks_like_garbage_title` (Task 1); `ContactDetail` (Task 2); existing `_get_or_create_address_entity(db, item, owner_id) -> Entity | None` (unchanged signature).
- Produces: `extract_entities()` now populates `ContactDetail` rows and `EntityRelationship.title` — consumed by Task 4's serialization.

- [x] **Step 1: Write the failing tests**

Append to `services/api/tests/test_entities.py`:

```python
async def test_extraction_creates_contact_detail_for_organization(client):
    """Karl Zimmer / Umbrella Corp letterhead case: phone + PO box + visiting
    address attach to the organization entity, with PO box/visiting address
    becoming their own deduped address entities via the existing machinery."""
    token = await _login(client, "entityuser-contact1")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Umbrella Corp letterhead")
    fake = (
        '{"entities": [{"name": "Umbrella Corp", "type": "organization", '
        '"phone": "010-1234567", "po_box": "Postbus 99, 1000 AB Amsterdam", '
        '"visiting_address": "Hoofdstraat 1, 1011 AB Amsterdam"}], "relationships": []}'
    )

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert len(entities) == 1
    contact = entities[0]["contact"]
    assert contact["phone"] == "010-1234567"
    assert contact["po_box_address"] is not None
    assert contact["po_box_address"]["city"] == "Amsterdam"
    assert contact["visiting_address"] is not None
    assert contact["visiting_address"]["street"] == "Hoofdstraat"


async def test_contact_detail_gap_fills_across_documents_not_overwrite(client):
    token = await _login(client, "entityuser-contact2")
    headers = {"Authorization": f"Bearer {token}"}
    doc1 = await _upload_ready_document(client, headers, "First letter")
    fake1 = '{"entities": [{"name": "Acme BV", "type": "organization", "phone": "010-1234567"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake1):
        r1 = await client.post(f"/documents/{doc1}/extract-entities", headers=headers)
    assert r1.json()[0]["contact"]["phone"] == "010-1234567"

    doc2 = await _upload_ready_document(client, headers, "Second letter")
    fake2 = '{"entities": [{"name": "Acme BV", "type": "organization", "phone": "999-9999999"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake2):
        r2 = await client.post(f"/documents/{doc2}/extract-entities", headers=headers)

    assert r2.json()[0]["contact"]["phone"] == "010-1234567"


async def test_extraction_rejects_garbage_phone_and_title(client):
    token = await _login(client, "entityuser-contact3")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Third letter")
    fake = (
        '{"entities": [{"name": "Karl Zimmer", "type": "person", "phone": "info@acme.com"}, '
        '{"name": "Acme BV", "type": "organization"}], '
        '"relationships": [{"source": "Karl Zimmer", "target": "Acme BV", "type": "employee_of", '
        '"title": "https://acme.com"}]}'
    )

    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    entities_by_name = {e["name"]: e for e in extracted.json()}
    assert entities_by_name["Karl Zimmer"]["contact"] is None

    person_id = entities_by_name["Karl Zimmer"]["id"]
    org_id = entities_by_name["Acme BV"]["id"]
    await client.post(f"/entities/{person_id}/approve", headers=headers)
    await client.post(f"/entities/{org_id}/approve", headers=headers)
    graph = await client.get(f"/entities/{person_id}/graph", headers=headers)
    assert graph.json()["edges"][0]["title"] is None


async def test_relationship_title_is_extracted_and_serialized_in_graph(client):
    token = await _login(client, "entityuser-title1")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Karl Zimmer, Directeur bij Umbrella Corp.")
    fake = (
        '{"entities": [{"name": "Karl Zimmer", "type": "person"}, {"name": "Umbrella Corp", "type": "organization"}], '
        '"relationships": [{"source": "Karl Zimmer", "target": "Umbrella Corp", "type": "employee_of", "title": "Directeur"}]}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    entities_by_name = {e["name"]: e["id"] for e in extracted.json()}
    await client.post(f"/entities/{entities_by_name['Karl Zimmer']}/approve", headers=headers)
    await client.post(f"/entities/{entities_by_name['Umbrella Corp']}/approve", headers=headers)

    graph = await client.get(f"/entities/{entities_by_name['Karl Zimmer']}/graph", headers=headers)
    edge = graph.json()["edges"][0]
    assert edge["title"] == "Directeur"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api pytest tests/test_entities.py -k "contact_detail or garbage_phone or relationship_title" -v`
Expected: FAIL — `entities[0]["contact"]` key error / `edge["title"]` key error (fields don't exist yet).

- [x] **Step 3: Implement**

In `services/api/src/api/entity_agent.py`, update imports:

```python
from api.address_parser import parse_address
from api.ai_gateway import chat_completion
from api.contact_parser import looks_like_garbage_title, parse_phone
from api.models import AddressDetail, Category, ContactDetail, Document, Entity, EntityMention, EntityRelationship, Residency
```

Replace `EXTRACTION_PROMPT`:

```python
EXTRACTION_PROMPT = """Extract people, organizations, locations, and specific addresses \
mentioned in the following document. Return ONLY a JSON object (no prose, no markdown \
fences) with this shape:

{{"entities": [{{"name": str, "type": "person"|"organization"|"location"|"address", \
"street": str|null, "house_number": str|null, "postal_code": str|null, "city": str|null, \
"country": str|null, "phone": str|null, "po_box": str|null, "visiting_address": str|null}}], \
"relationships": [{{"source": str, "target": str, "type": str, "title": str|null}}]}}

The "street"/"house_number"/"postal_code"/"city"/"country" fields only apply to \
type "address" entities; omit or null them for every other type.

"phone" is a candidate phone number mentioned near a "person" or "organization" entity, \
as raw text exactly as written (e.g. "010-1234567"). "po_box" and "visiting_address" are \
candidate address text mentioned near an "organization" entity (e.g. a PO box line or a \
visiting/establishment address on a letterhead), as raw text exactly as written. Omit or \
null all three for every other type.

"title" on a relationship is the person's job title at the organization, if the document \
states one (e.g. "Directeur"), otherwise null. Only meaningful for person-to-organization \
relationships.

"source" and "target" must exactly match a "name" from the entities list. If there are no \
entities, return {{"entities": [], "relationships": []}}.

Document:
{text}"""
```

Replace `EXTRACTION_SCHEMA`:

```python
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["person", "organization", "location", "address"]},
                    "street": {"type": ["string", "null"]},
                    "house_number": {"type": ["string", "null"]},
                    "postal_code": {"type": ["string", "null"]},
                    "city": {"type": ["string", "null"]},
                    "country": {"type": ["string", "null"]},
                    "phone": {"type": ["string", "null"]},
                    "po_box": {"type": ["string", "null"]},
                    "visiting_address": {"type": ["string", "null"]},
                },
                "required": ["name", "type"],
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "type": {"type": "string"},
                    "title": {"type": ["string", "null"]},
                },
                "required": ["source", "target", "type"],
            },
        },
    },
    "required": ["entities", "relationships"],
}
```

Add two new helpers after `_get_or_create_address_entity` (~line 251, before `_update_residency`):

```python
async def _add_mention_if_missing(db: AsyncSession, *, entity_id: UUID, document_id: UUID) -> None:
    existing = await db.execute(
        select(EntityMention).where(EntityMention.entity_id == entity_id, EntityMention.document_id == document_id)
    )
    if existing.scalar_one_or_none() is None:
        db.add(EntityMention(entity_id=entity_id, document_id=document_id))


async def _upsert_contact_detail(
    db: AsyncSession, *, entity: Entity, item: dict, owner_id: UUID, document_id: UUID
) -> None:
    """Gap-fill ContactDetail for a person/organization entity from one extraction's
    phone/po_box/visiting_address candidates -- never overwrites an already-populated
    field, same rule _get_or_create_address_entity uses for AddressDetail. PO box and
    visiting address become their own deduped address entities via the existing
    address machinery, each getting an EntityMention on this document for traceability.

    Validates candidates *before* touching the database: if every candidate on this
    extraction fails validation (e.g. an email mis-slotted into "phone"), no
    ContactDetail row is created at all -- an all-None row would otherwise serialize
    as a non-null but empty `contact`, indistinguishable from a real one to callers.
    """
    raw_phone = item.get("phone")
    raw_po_box = item.get("po_box")
    raw_visiting_address = item.get("visiting_address")
    if not raw_phone and not raw_po_box and not raw_visiting_address:
        return

    phone = parse_phone(str(raw_phone)) if raw_phone else None
    po_box_entity = await _get_or_create_address_entity(db, {"name": str(raw_po_box)}, owner_id) if raw_po_box else None
    visiting_entity = (
        await _get_or_create_address_entity(db, {"name": str(raw_visiting_address)}, owner_id)
        if raw_visiting_address else None
    )
    if phone is None and po_box_entity is None and visiting_entity is None:
        return

    detail = await db.get(ContactDetail, entity.id)
    if detail is None:
        detail = ContactDetail(entity_id=entity.id)
        db.add(detail)
        await db.flush()

    if detail.phone is None and phone is not None:
        detail.phone = phone
    if detail.po_box_address_entity_id is None and po_box_entity is not None:
        detail.po_box_address_entity_id = po_box_entity.id
        await _add_mention_if_missing(db, entity_id=po_box_entity.id, document_id=document_id)
    if detail.visiting_address_entity_id is None and visiting_entity is not None:
        detail.visiting_address_entity_id = visiting_entity.id
        await _add_mention_if_missing(db, entity_id=visiting_entity.id, document_id=document_id)
```

In `extract_entities()`, replace the existing inline mention-check block:

```python
        existing = await db.execute(
            select(EntityMention).where(EntityMention.entity_id == entity.id, EntityMention.document_id == document_id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(EntityMention(entity_id=entity.id, document_id=document_id))
```

with:

```python
        await _add_mention_if_missing(db, entity_id=entity.id, document_id=document_id)
        if entity_type in ("person", "organization"):
            await _upsert_contact_detail(db, entity=entity, item=item, owner_id=user_id, document_id=document_id)
```

In the relationship-persisting loop, replace:

```python
    for rel in raw_relationships:
        if not isinstance(rel, dict) or not rel.get("source") or not rel.get("target") or not rel.get("type"):
            continue
        source = entities_by_name.get(str(rel["source"]).strip().lower())
        target = entities_by_name.get(str(rel["target"]).strip().lower())
        if source is None or target is None:
            continue
        db.add(
            EntityRelationship(
                source_entity_id=source.id,
                target_entity_id=target.id,
                relationship_type=str(rel["type"])[:255],
                document_id=document_id,
            )
        )
```

with:

```python
    for rel in raw_relationships:
        if not isinstance(rel, dict) or not rel.get("source") or not rel.get("target") or not rel.get("type"):
            continue
        source = entities_by_name.get(str(rel["source"]).strip().lower())
        target = entities_by_name.get(str(rel["target"]).strip().lower())
        if source is None or target is None:
            continue
        raw_title = rel.get("title")
        title = str(raw_title)[:255] if raw_title and not looks_like_garbage_title(str(raw_title)) else None
        db.add(
            EntityRelationship(
                source_entity_id=source.id,
                target_entity_id=target.id,
                relationship_type=str(rel["type"])[:255],
                document_id=document_id,
                title=title,
            )
        )
```

(Task 4 adds the `contact`/`title` fields to the response models these tests assert on — run this task's tests again after Task 4 if any still fail on serialization.)

- [x] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api pytest tests/test_entities.py -k "contact_detail or garbage_phone or relationship_title" -v`
Expected: PASS once Task 4's serialization changes are also in place (these two tasks are tightly coupled — implement Task 4 immediately after this step if tests still fail on missing `contact`/`title` response fields).

- [x] **Step 5: Commit**

```bash
git add services/api/src/api/entity_agent.py services/api/tests/test_entities.py
git commit -m "feat: extract phone/PO-box/visiting-address/title into ContactDetail and EntityRelationship"
```

---

### Task 4: API surface — `entities.py`

**Files:**
- Modify: `services/api/src/api/entities.py`

**Interfaces:**
- Consumes: `ContactDetail` (Task 2), `AddressOut` from `api.residencies_router` (existing, has `maps_url`).
- Produces: `EntityOut.contact: ContactDetailOut | None`, `GraphEdge.title: str | None` — consumed by Task 3's tests and Task 5's frontend types.

- [x] **Step 1: Implement**

In `services/api/src/api/entities.py`, update imports:

```python
from api.address_parser import build_maps_url
from api.auth import get_effective_user
from api.db import get_db
from api.entity_agent import VALID_ENTITY_TYPES, extract_entities
from api.models import AddressDetail, ContactDetail, Document, Entity, EntityMention, EntityMergeLog, EntityRelationship, User
from api.residencies_router import AddressOut
```

Replace the `EntityOut` class (and add `ContactDetailOut` + a small helper before it):

```python
class ContactDetailOut(BaseModel):
    phone: str | None
    po_box_address: AddressOut | None
    visiting_address: AddressOut | None


async def _address_out(db: AsyncSession, entity_id: UUID | None) -> AddressOut | None:
    if entity_id is None:
        return None
    entity = await db.get(Entity, entity_id)
    detail = await db.get(AddressDetail, entity_id)
    if entity is None or detail is None:
        return None
    return AddressOut(
        id=entity.id, name=entity.name, street=detail.street, house_number=detail.house_number,
        postal_code=detail.postal_code, city=detail.city, country=detail.country,
        maps_url=build_maps_url(
            street=detail.street, house_number=detail.house_number,
            postal_code=detail.postal_code, city=detail.city, country=detail.country,
        ),
    )


class EntityOut(BaseModel):
    id: UUID
    name: str
    entity_type: str
    status: str
    created_at: datetime
    maps_url: str | None = None
    contact: ContactDetailOut | None = None

    @classmethod
    async def from_entity(cls, db: AsyncSession, entity: Entity) -> "EntityOut":
        maps_url = None
        if entity.entity_type == "address":
            detail = await db.get(AddressDetail, entity.id)
            if detail is not None:
                maps_url = build_maps_url(
                    street=detail.street, house_number=detail.house_number,
                    postal_code=detail.postal_code, city=detail.city, country=detail.country,
                )
        contact = None
        if entity.entity_type in ("person", "organization"):
            contact_detail = await db.get(ContactDetail, entity.id)
            if contact_detail is not None:
                contact = ContactDetailOut(
                    phone=contact_detail.phone,
                    po_box_address=await _address_out(db, contact_detail.po_box_address_entity_id),
                    visiting_address=await _address_out(db, contact_detail.visiting_address_entity_id),
                )
        return cls(
            id=entity.id, name=entity.name, entity_type=entity.entity_type,
            status=entity.status, created_at=entity.created_at, maps_url=maps_url, contact=contact,
        )
```

Update `GraphEdge` to include `title`:

```python
class GraphEdge(BaseModel):
    source: UUID
    target: UUID
    relationship_type: str
    title: str | None
    document_id: UUID | None
```

Update the `edges=[...]` construction in `get_entity_graph`:

```python
        edges=[
            GraphEdge(
                source=edge.source_entity_id,
                target=edge.target_entity_id,
                relationship_type=edge.relationship_type,
                title=edge.title,
                document_id=edge.document_id,
            )
            for edge in edges
        ],
```

- [x] **Step 2: Run the full entity test suite**

Run: `docker compose exec api pytest tests/test_entities.py -v`
Expected: PASS — includes Task 3's four new tests plus all pre-existing entity tests (no regressions).

- [x] **Step 3: Commit**

```bash
git add services/api/src/api/entities.py
git commit -m "feat: serialize ContactDetail and relationship title in entity API"
```

---

### Task 5: Frontend types and graph display

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/routes/EntityGraph.tsx`
- Modify: `apps/web/src/routes/Entities.test.tsx`, `apps/web/src/routes/EntityReview.test.tsx`, `apps/web/src/routes/EntityGraph.test.tsx` (fixtures need the new required fields)

**Interfaces:**
- Consumes: the JSON shapes Task 4 now returns (`EntityOut.contact`, `GraphEdge.title`).

- [x] **Step 1: Update `apps/web/src/lib/api.ts`**

Add `AddressOut` reference and update `EntityOut` (~line 375):

```typescript
export interface ContactDetailOut {
  phone: string | null;
  po_box_address: AddressOut | null;
  visiting_address: AddressOut | null;
}

export interface EntityOut {
  id: string;
  name: string;
  entity_type: string;
  status: string;
  created_at: string;
  maps_url: string | null;
  contact: ContactDetailOut | null;
}
```

`AddressOut` is defined later in the same file (~line 1047); TypeScript interfaces in a single module don't need declaration-order, so no import reordering is needed.

Update `GraphEdge` (~line 430):

```typescript
export interface GraphEdge {
  source: string;
  target: string;
  relationship_type: string;
  title: string | null;
  document_id: string | null;
}
```

- [x] **Step 2: Render relationship title in `EntityGraph.tsx`**

In `apps/web/src/routes/EntityGraph.tsx` (~line 113-115), change:

```tsx
                  <text x={mid.x} y={mid.y} textAnchor="middle" fontSize={10} fill="var(--text-2)" className="select-none">
                    {edge.relationship_type}
                  </text>
```

to:

```tsx
                  <text x={mid.x} y={mid.y} textAnchor="middle" fontSize={10} fill="var(--text-2)" className="select-none">
                    {edge.title ? `${edge.relationship_type} (${edge.title})` : edge.relationship_type}
                  </text>
```

- [x] **Step 3: Fix existing test fixtures**

In `apps/web/src/routes/Entities.test.tsx` and `apps/web/src/routes/EntityReview.test.tsx`, every `EntityOut` fixture object (e.g. `{ id: "e1", name: "Jane Smith", ..., maps_url: null }`) needs `contact: null` added. Example for `Entities.test.tsx`:

```typescript
{ id: "e1", name: "Jane Smith", entity_type: "person", status: "confirmed", created_at: "2026-01-01T00:00:00Z", maps_url: null, contact: null },
{ id: "e2", name: "Acme Corp", entity_type: "organization", status: "confirmed", created_at: "2026-01-02T00:00:00Z", maps_url: null, contact: null },
```

Apply the same `contact: null` addition to every `EntityOut`-shaped fixture in `EntityReview.test.tsx`. In `EntityGraph.test.tsx`, add `title: null` (or a specific string where a test wants to assert on it) to every `GraphEdge`-shaped fixture.

- [x] **Step 4: Run frontend tests**

Run: `docker compose exec web sh -c 'cd /app/apps/web && npx vitest run src/routes/Entities.test.tsx src/routes/EntityReview.test.tsx src/routes/EntityGraph.test.tsx'`
Expected: PASS. Fix any TypeScript errors from missing fields by adding them to the flagged fixtures.

- [x] **Step 5: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/routes/EntityGraph.tsx apps/web/src/routes/Entities.test.tsx apps/web/src/routes/EntityReview.test.tsx apps/web/src/routes/EntityGraph.test.tsx
git commit -m "feat: surface contact details and relationship title in frontend"
```

---

### Task 6: Deploy and verify

**Files:** none (operational task)

- [x] **Step 1: Rebuild and restart the API container, apply the migration**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose up -d api"
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T api alembic upgrade head"
```

Expected: `api` container restarts healthy (bind-mounted source picked up by `--reload`); migration `5dd392e03c44` applies against production Postgres with no errors.

- [x] **Step 2: Rebuild the frontend**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T web sh -c 'cd /app/apps/web && npx vite build'"
```

Expected: build succeeds with no TypeScript errors.

- [x] **Step 3: Verify production health**

```bash
ssh root@178.254.22.178 "curl -s -o /dev/null -w 'HTTP %{http_code}\n' https://collabrains.eu/"
ssh root@178.254.22.178 "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

Expected: `HTTP 200`; all containers `Up`/`healthy`.

- [x] **Step 4: Re-run the full backend test suite against the live DB one more time**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_contact_parser.py tests/test_entities.py -v"
```

Expected: PASS. If pytest isn't installed in the container (known recurring issue after container recreation), run `docker compose exec -T api pip install --no-cache-dir pytest pytest-asyncio` first.

- [x] **Step 5: Commit and push**

```bash
git log --oneline -6
git push origin main
```

Expected: all 5 feature commits (Tasks 1-5) plus the earlier spec commit push cleanly to `origin/main`.
