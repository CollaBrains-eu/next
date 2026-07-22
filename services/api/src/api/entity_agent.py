"""Entity Agent: extract entities and relationships from a document's text.

See docs/adr/0008-phase4-entity-graph.md for scope: exact case-insensitive
name+type dedup only (no fuzzy/LLM-based entity resolution), relationships
only kept when both endpoints appear in the same extraction's entity list.

Address entities (docs/superpowers/plans/2026-07-11-entity-address-history.md)
extend this with a second dedup path (structured-field normalization instead
of name matching) and a side effect: extracting an address from a document
in `RESIDENCE_CATEGORY_SLUGS` updates the owning user's `Residency` timeline.
"""
import json
import logging
import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.address_parser import parse_address
from api.ai_gateway import chat_completion
from api.models import AddressDetail, Category, Document, Entity, EntityMention, EntityRelationship, Residency

logger = logging.getLogger(__name__)

VALID_ENTITY_TYPES = {"person", "organization", "location", "address", "other"}

# Only these two types are trustworthy enough to auto-create from a bulk per-document LLM
# scan without a human in the loop first -- organizations feed case-correspondent linking,
# addresses feed the residency timeline below. Person/location/other entities were the
# dominant source of low-quality "random entity" noise (see
# docs/superpowers/specs/2026-07-09-entity-review-queue-design.md) and are now manual-only,
# created via POST /entities in entities.py instead.
AUTO_EXTRACTED_ENTITY_TYPES = {"organization", "address"}

# Documents where an extracted address is very likely the user's own current
# address, not a third party's (e.g. a landlord on a rental contract, or a
# store on an invoice) -- residency detection only fires for these, contract
# documents get linked to the resulting residency period once it exists.
RESIDENCE_CATEGORY_SLUGS = {"identity_document", "mortgage_housing", "rental_contract", "government"}
CONTRACT_CATEGORY_SLUGS = {"rental_contract", "mortgage_housing", "employment_contract"}

# Code-level guardrail, not prompt-only -- this project's own established lesson
# (ai_gateway.py's json_mode docstring) is that prompt instructions alone are not
# reliable on a small local model. Live production data had an email, a URL, and a
# person-salutation line all extracted as entity_type="address" despite the prompt
# explicitly saying "Do not extract people's names."
_GARBAGE_ADDRESS_RE = re.compile(
    r"@|https?://|www\.|\bt\.a\.v\.|\bde heer\b|\bmevrouw\b|\bdhr\.|\bmw\.",
    re.IGNORECASE,
)


def _looks_like_garbage_address(name: str) -> bool:
    return bool(_GARBAGE_ADDRESS_RE.search(name))

EXTRACTION_PROMPT = """Extract organizations and specific addresses mentioned in the \
following document. Do not extract people's names or generic locations -- only \
organizations and addresses. Return ONLY a JSON object (no prose, no markdown fences) \
with this shape:

{{"entities": [{{"name": str, "type": "organization"|"address", \
"street": str|null, "house_number": str|null, "postal_code": str|null, "city": str|null, \
"country": str|null}}], "relationships": [{{"source": str, "target": str, "type": str}}]}}

The "street"/"house_number"/"postal_code"/"city"/"country" fields only apply to \
type "address" entities; omit or null them for "organization".

"source" and "target" must exactly match a "name" from the entities list. If there are no \
entities, return {{"entities": [], "relationships": []}}.

Document:
{text}"""

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["organization", "address"]},
                    "street": {"type": ["string", "null"]},
                    "house_number": {"type": ["string", "null"]},
                    "postal_code": {"type": ["string", "null"]},
                    "city": {"type": ["string", "null"]},
                    "country": {"type": ["string", "null"]},
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
                },
                "required": ["source", "target", "type"],
            },
        },
    },
    "required": ["entities", "relationships"],
}


def _normalize_address_key(item: dict) -> str:
    postal = str(item.get("postal_code") or "").strip().lower()
    house = str(item.get("house_number") or "").strip().lower()
    street = str(item.get("street") or item.get("name") or "").strip().lower()
    return f"{postal}|{house}|{street}"


async def _get_or_create_entity(db: AsyncSession, name: str, entity_type: str, owner_id: UUID) -> Entity | None:
    """Look up an existing entity by case-insensitive (name, entity_type), scoped to
    `owner_id` -- entities are per-account (Phase 28), not a system-wide graph, so two
    different accounts extracting "Acme Corp" get two independent rows.

    Returns the existing row if it is `confirmed` or `pending_review`
    (reusing it rather than creating a duplicate pending row), `None` if
    it is `rejected` (permanently suppressed -- see
    docs/superpowers/specs/2026-07-09-entity-review-queue-design.md), or
    creates a new `pending_review` row if there is no match at all.
    """
    result = await db.execute(
        select(Entity).where(
            func.lower(Entity.name) == name.lower().strip(),
            Entity.entity_type == entity_type,
            Entity.owner_id == owner_id,
        )
    )
    entity = result.scalar_one_or_none()
    if entity is not None:
        if entity.status == "rejected":
            return None
        return entity
    entity = Entity(name=name.strip(), entity_type=entity_type, owner_id=owner_id)
    db.add(entity)
    await db.flush()
    return entity


async def _get_or_create_address_entity(db: AsyncSession, item: dict, owner_id: UUID) -> Entity | None:
    """Same contract as `_get_or_create_entity`, but dedups address entities by
    normalized structured fields (still scoped to `owner_id`) instead of exact name
    match -- two LLM extractions of the same real address rarely render as identical
    text. Rejects candidates that look like an email/URL/person-salutation before
    ever creating an Entity row (see _looks_like_garbage_address)."""
    raw_name = str(item.get("name") or "").strip()
    if _looks_like_garbage_address(raw_name):
        logger.info("entity_agent: rejected garbage address candidate %r", raw_name)
        return None

    parsed = parse_address(raw_name)
    # Prefer the LLM's own structured fields when present (schema-constrained, so
    # at least well-typed when given), fall back to the deterministic parser for
    # whatever it left null -- live data showed the LLM leaves these null far more
    # often than it fills them.
    filled_item = {
        "name": raw_name,
        "street": item.get("street") or parsed["street"],
        "house_number": item.get("house_number") or parsed["house_number"],
        "postal_code": item.get("postal_code") or parsed["postal_code"],
        "city": item.get("city") or parsed["city"],
        "country": item.get("country") or parsed["country"],
    }

    normalized_key = _normalize_address_key(filled_item)
    result = await db.execute(
        select(Entity).join(AddressDetail, AddressDetail.entity_id == Entity.id).where(
            AddressDetail.normalized_key == normalized_key, Entity.owner_id == owner_id
        )
    )
    entity = result.scalar_one_or_none()
    if entity is not None:
        if entity.status == "rejected":
            return None
        return entity

    entity = Entity(name=raw_name or normalized_key, entity_type="address", owner_id=owner_id)
    db.add(entity)
    await db.flush()
    db.add(
        AddressDetail(
            entity_id=entity.id,
            street=filled_item["street"],
            house_number=filled_item["house_number"],
            postal_code=filled_item["postal_code"],
            city=filled_item["city"],
            country=filled_item["country"],
            normalized_key=normalized_key,
        )
    )
    return entity


async def _update_residency(db: AsyncSession, *, user_id: UUID, address_entity_id: UUID, document_id: UUID) -> Residency:
    """Update the user's residency timeline given a newly-extracted address.

    No-op if it matches the current (`valid_to IS NULL`) residency.
    Otherwise closes the current period and opens a new one, both left
    `pending_review` -- a single document mentioning an address is evidence
    of a move, not proof; a human confirms via the same review-queue
    pattern already used for entities.
    """
    result = await db.execute(select(Residency).where(Residency.user_id == user_id, Residency.valid_to.is_(None)))
    current = result.scalar_one_or_none()

    doc_result = await db.execute(select(Document.created_at).where(Document.id == document_id))
    document_date = doc_result.scalar_one().date()

    if current is not None and current.address_entity_id == address_entity_id:
        return current

    if current is not None:
        current.valid_to = document_date

    new_residency = Residency(
        user_id=user_id,
        address_entity_id=address_entity_id,
        valid_from=document_date,
        source_document_id=document_id,
        status="pending_review",
    )
    db.add(new_residency)
    await db.flush()
    return new_residency


async def _maybe_link_contract(db: AsyncSession, *, document_id: UUID, user_id: UUID, category_slug: str | None) -> None:
    """Link a contract-category document to the user's current residency.

    Independent of whether *this* document also revealed a new address --
    an employment contract, for instance, is never itself a source of
    residency detection (RESIDENCE_CATEGORY_SLUGS), but should still get
    linked to whatever the user's current residency already is.
    """
    if category_slug not in CONTRACT_CATEGORY_SLUGS:
        return
    result = await db.execute(select(Residency).where(Residency.user_id == user_id, Residency.valid_to.is_(None)))
    residency = result.scalar_one_or_none()
    if residency is None:
        return
    document = await db.get(Document, document_id)
    if document is not None and document.residency_id is None:
        document.residency_id = residency.id


async def extract_entities(db: AsyncSession, *, document_id: UUID, text: str, user_id: UUID) -> list[Entity]:
    """Extract entities/relationships from `text` via the AI Gateway and persist them."""
    prompt = EXTRACTION_PROMPT.format(text=text[:8000])
    raw = await chat_completion(
        [{"role": "user", "content": prompt}],
        user_id=user_id,
        endpoint="entity.extract",
        schema=EXTRACTION_SCHEMA,
    )

    try:
        payload = json.loads(raw)
        raw_entities = payload.get("entities", [])
        raw_relationships = payload.get("relationships", [])
        if not isinstance(raw_entities, list) or not isinstance(raw_relationships, list):
            raise ValueError("entities/relationships must be arrays")
    except (json.JSONDecodeError, ValueError, AttributeError):
        logger.warning("entity_agent: could not parse extraction output: %r", raw[:500])
        return []

    document_category = await db.execute(
        select(Category.slug).join(Document, Document.category_id == Category.id).where(Document.id == document_id)
    )
    category_slug = document_category.scalar_one_or_none()

    entities_by_name: dict[str, Entity] = {}
    persisted: list[Entity] = []
    address_entity_ids: list[UUID] = []
    for item in raw_entities:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        entity_type = item.get("type") if item.get("type") in VALID_ENTITY_TYPES else "other"
        if entity_type not in AUTO_EXTRACTED_ENTITY_TYPES:
            continue
        if entity_type == "address":
            entity = await _get_or_create_address_entity(db, item, user_id)
        else:
            entity = await _get_or_create_entity(db, item["name"], entity_type, user_id)
        if entity is None:
            continue  # rejected entity, permanently suppressed
        entities_by_name[item["name"].strip().lower()] = entity
        persisted.append(entity)
        if entity_type == "address":
            address_entity_ids.append(entity.id)

        existing = await db.execute(
            select(EntityMention).where(EntityMention.entity_id == entity.id, EntityMention.document_id == document_id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(EntityMention(entity_id=entity.id, document_id=document_id))

    if address_entity_ids and category_slug in RESIDENCE_CATEGORY_SLUGS:
        # Ambiguous which address is the user's own if several were found
        # (e.g. landlord + property on one rental contract) -- take the
        # first, still `pending_review` so a human can correct it.
        await _update_residency(db, user_id=user_id, address_entity_id=address_entity_ids[0], document_id=document_id)

    await _maybe_link_contract(db, document_id=document_id, user_id=user_id, category_slug=category_slug)

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

    await db.commit()
    for entity in persisted:
        await db.refresh(entity)
    return persisted
