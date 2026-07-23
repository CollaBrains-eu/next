# LDAP-Style Relational Contact Details — Design

**Status:** Approved
**Related:** `docs/superpowers/specs/2026-07-23-reliable-entity-extraction-maps-design.md` (address parsing/dedup this design reuses)

## Problem

Documents frequently name a person affiliated with an organization along with
richer contact context than a bare name — e.g. "Karl Zimmer, Directeur,
tel. 010-1234567" for an organization whose letterhead also carries a PO box
and a separate visiting/establishment address. None of this is captured
today: `Entity(entity_type="person"|"organization")` rows only ever get a
`name`. The feature was requested explicitly as **relational** (LDAP-style
attribute richness), not a JSONB blob, so it can be queried, deduped, and
merged like every other entity attribute in this system.

## Schema

### `ContactDetail`

One row per entity (same 1:1 pattern as `AddressDetail`), attachable to
`entity_type in ("person", "organization")`:

```python
class ContactDetail(Base):
    """Structured contact fields for an Entity where entity_type is 'person' or
    'organization'. One row per entity (same 1:1 pattern as AddressDetail) --
    gap-filled across documents, never fragmented into duplicates."""

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

PO box and visiting address are FKs to `entities.id` (type `address`), not
raw text — this reuses the parsing, dedup, `maps_url`, and review-queue
machinery `address_parser.py` and `_get_or_create_address_entity` /
`_find_matching_address_entity` already built, rather than duplicating it.
No separate `country` field: country is read off the visiting address's
`AddressDetail.country` to avoid two country values disagreeing.

### `EntityRelationship.title`

```python
title: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

A person's title (e.g. "Directeur") is contextual to a specific
person→organization relationship, not a global fact about the person — the
same person could hold different titles at different organizations across
documents. `EntityRelationship` rows are already append-only evidence
(one new row per document scan, no dedup), so `title` needs no merge logic:
each extraction just records what that document said.

## Extraction Pipeline

Extends the existing single-pass LLM extraction in `entity_agent.py` rather
than adding a second pass:

- `EXTRACTION_SCHEMA` entity items (any type) gain optional `phone`,
  `po_box`, `visiting_address` — raw text snippets, not yet structured.
- `EXTRACTION_SCHEMA` relationship items gain optional `title`.

Field-structuring stays deterministic, per this project's established
lesson (`ai_gateway.py`'s `json_mode` docstring) that small local models
don't reliably split fields themselves — the same reasoning that produced
`address_parser.py` for addresses:

- New `contact_parser.py` (sibling to `address_parser.py`):
  - `parse_phone(raw_text) -> str | None`: normalizes a candidate phone
    snippet (digits, spaces, `+`, `-`, parens) to a cleaned string, or
    `None` if it doesn't look like a phone number.
  - `_looks_like_garbage_title(text) -> bool`: same guardrail pattern as
    `_looks_like_garbage_address` — rejects titles that are too long or
    contain `@`/`http` (an LLM occasionally mis-slots an email or URL into
    the wrong field).
- `po_box` / `visiting_address` raw text is run through the *existing*
  `address_parser.parse_address()` then `_get_or_create_address_entity()`
  to become a deduped address `Entity`, exactly like a top-level address
  extraction.
- `ContactDetail` upsert is gap-fill only: an already-populated field is
  never overwritten by a later, less-complete extraction — same rule
  `_find_matching_address_entity` established for `AddressDetail`.

## API / Frontend Surface

```python
class ContactDetailOut(BaseModel):
    phone: str | None
    po_box_address: AddressOut | None
    visiting_address: AddressOut | None

class EntityOut(BaseModel):
    ...
    contact: ContactDetailOut | None
```

Reuses `AddressOut` (including its `maps_url`) for both nested addresses, so
a PO box or visiting address is map-linkable the same way a residency
already is. Relationship `title` is added to the existing relationship
serializer and surfaces wherever relationships are already listed (entity
detail/graph view) — no new endpoint.

## Migration

One Alembic migration: create `contact_details`, add `title` column to
`entity_relationships`.

## Testing

Same TDD pattern as the address-extraction work:
- `test_contact_parser.py`: phone normalization, garbage-title guardrail.
- `test_entities.py` extensions: extraction creates/gap-fills
  `ContactDetail`, rejects garbage phone/title, relationship rows carry
  `title`.
- Entity-serialization tests for the new `contact` field on `EntityOut`.

## Out of Scope

- Multiple phone numbers per entity (one row per entity, same as
  `AddressDetail` — YAGNI until a real document shows two numbers that
  both need to be kept).
- Syncing any of this into the OpenLDAP directory service (`ldap_auth.py`)
  — that LDAP is strictly user authentication and is unrelated to this
  feature; "LDAP-style" here refers only to attribute richness as
  inspiration for the Postgres schema.
