# Plan: entity address history & contract-period linking

## Goal

The current `Entity` model (ADR 0008) only stores `name` + `entity_type`,
deduplicated by exact case-insensitive match. Addresses are extracted as
plain `entity_type="location"` strings with no structure and no history --
the system has no way to know that "Kerkstraat 12, Amsterdam" and
"Kerkstraat 12, 1012AB Amsterdam" are the same address, no way to know a
user moved from one address to another, and no way to say "this rental
contract applied while the user lived at address X, not their current one."

This plan adds a temporal residency model: a user's addresses over time,
each with a validity period, detected automatically as documents reveal
new addresses, and used to scope contract documents to the period/address
they actually applied to.

## Non-goals (this PR)

- Fuzzy/LLM-based address resolution beyond structured-field matching --
  ADR 0008 deliberately keeps entity dedup simple; this plan extends that
  same philosophy to addresses (dedup by normalized postal_code +
  house_number, not fuzzy string matching).
- Tracking address history for entities that are *not* CollaBrains users
  (e.g. a landlord or family member mentioned in a document). Only
  `users.id`-linked residency is in scope -- extending to arbitrary
  person-entities is a natural follow-up but adds a second axis of
  complexity (which extracted "person" *is* this user?) not needed to
  satisfy the request.
- Automatic effective-date extraction from contract text (e.g. "lease
  starts 1 March 2026"). First cut ties a contract to the residency
  period that was current when the document was uploaded; refining this
  with LLM-extracted effective dates is a follow-up once the base
  plumbing exists and can be evaluated against real documents.

## Data model

### `Entity.entity_type` gains `"address"`

Added to `VALID_ENTITY_TYPES` in `entity_agent.py` alongside
`person`/`organization`/`location`/`other`. Kept as a real `Entity` row
(not a separate table from scratch) so address entities get mentions,
appear in the entity graph, and go through the existing review-queue
(`pending_review` -> `confirmed`/`rejected`) for free.

### New table: `address_details`

One row per `Entity` where `entity_type = 'address'`, holding the
structured fields the LLM extraction step is asked for:

```python
class AddressDetail(Base):
    __tablename__ = "address_details"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    house_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    normalized_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
```

`normalized_key` = `lower(postal_code or '') + '|' + lower(house_number or '') + '|' + lower(street or name)`,
computed at extraction time. Dedup for address entities uses this key
instead of `Entity.name` exact-match, so formatting differences in how
the LLM renders the same address as text don't create duplicate entities.
Same `pending_review`/`confirmed`/`rejected` status flow as any other
entity -- a bad address extraction is rejectable through the existing
review queue UI, no new UI needed for that part.

### New table: `residencies`

The temporal join between a user and the addresses they've lived at:

```python
class Residency(Base):
    __tablename__ = "residencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    address_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)  # NULL = current
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review", server_default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Partial unique index: at most one row per `user_id` with `valid_to IS
NULL` (at most one "current" address at a time) -- enforced at the DB
level, not just application logic, the same discipline as the
`pending_user_phone_numbers` uniqueness bug caught last session.

### `documents.residency_id`

```python
residency_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("residencies.id", ondelete="SET NULL"), nullable=True
)
```

Nullable, `SET NULL` on residency delete -- a document should never block
or cascade-delete just because its residency link goes away.

## Detection logic (`entity_agent.py`)

`extract_entities` already runs per uploaded document and persists
`person`/`organization`/`location`/`other` entities. This plan adds:

1. Extraction prompt gains an `"address"` type option, and when an entity
   of that type is returned, the LLM is asked for the structured
   sub-fields (single extra prompt field, not a second round-trip).
2. After persisting an `address`-type entity for a document owned by
   user U:
   - Compute `normalized_key`, look up an existing `AddressDetail` by
     that key (reuse if found, matching the existing `_get_or_create_entity`
     dedup pattern).
   - Look up U's current residency (`valid_to IS NULL`).
   - If none exists: create one, `valid_from = document.created_at.date()`,
     `status="pending_review"`.
   - If one exists and its `address_entity_id` differs from the new
     address: this is a detected relocation. Close the old row
     (`valid_to = document.created_at.date()`), open a new one
     (`valid_from = document.created_at.date()`). Both transitions are
     `pending_review` -- a single document mentioning a new address isn't
     strong enough evidence to silently overwrite history; a human
     confirms via the same review-queue pattern used for entities.
   - If one exists and matches: no-op (same address seen again).
3. Contract linking: if the document's `category` (via `categories`
   table, `category_type="document"`) is one of the "contract-like"
   slugs (`rental_contract`, `mortgage_housing`, `employment_contract` --
   the existing category list from `en.json`'s `categories` namespace),
   set `document.residency_id` to the user's current residency at
   upload time (creating a placeholder "unknown address" residency if
   none exists yet, so the link is never silently skipped).

## API surface

- `GET /users/me/residencies` (and admin equivalent `GET
  /admin/users/{user_id}/residencies`) -- ordered history, each row
  with its `AddressDetail` and the count/list of linked contract
  documents.
- `PATCH /residencies/{id}` -- admin/self correction (fix a wrong
  `valid_from`/`valid_to`, or approve/reject like other entities --
  reuses `_transition_entity`-style status transition, not a new
  pattern).
- Existing entity-review endpoints (`approve_entity`/`reject_entity`)
  already work for the underlying address `Entity` rows for free.

## Frontend

- New `AddressHistory` component (Violet DS: `Timeline`-style vertical
  list using existing card/border tokens, not a new primitive) showing
  each residency period, its address, date range, and linked contract
  documents (click-through to `DocumentDetail`).
- Surfaced on `Settings.tsx` (a user's own history) and as a new
  section in the Admin user detail (once a per-user admin detail view
  exists -- today Admin only lists users in a table; this plan adds a
  minimal detail expansion, not a full new route, to avoid scope creep).
- `EntityGraph.tsx`: address nodes get their own color in the existing
  categorical entity-type palette (same pattern as the four existing
  entity-type colors), consistent with how `location`/`person`/etc.
  are already distinguished.

## Migration

One Alembic revision: `address_details` + `residencies` tables,
`documents.residency_id` column, partial unique index on
`residencies(user_id) WHERE valid_to IS NULL`.

## Test plan

- Backend (real Postgres, no mocking): relocation detection (same
  address twice = no-op, different address = close+open), partial
  unique index enforcement, contract-category linking, normalized-key
  dedup across differently-formatted LLM output for the same real
  address, review-queue approve/reject on address entities.
- Frontend: `AddressHistory` component rendering, Settings integration,
  EntityGraph address-node coloring.

## Rollout

Single PR: migration + backend logic + tests + frontend. No feature
flag needed -- purely additive (new tables, new nullable column,
extends an existing entity_type enum), safe to ship and let organically
populate as new documents are processed. Existing documents are not
backfilled in this PR (would need re-running extraction against
`ocr_text` for ~10 real remaining documents post-cleanup -- worth doing
as a one-off admin script in a follow-up once the base feature is live
and confirmed working).
