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

from api.address_parser import find_full_address_matches, parse_address
from api.ai_gateway import chat_completion
from api.contact_parser import looks_like_garbage_title, parse_phone
from api.models import AddressDetail, Category, ContactDetail, Document, Entity, EntityMention, EntityRelationship, Residency

logger = logging.getLogger(__name__)

VALID_ENTITY_TYPES = {"person", "organization", "location", "address", "other"}

# Broadened 2026-07-23 to include person/location, now that a code-level guardrail
# exists (_looks_like_garbage_address et al) -- the 2026-07-09 pullback to
# organization/address only predates any such guardrail (prompt instructions alone
# weren't reliable). Deployed only after Tasks 1-4 of
# docs/superpowers/plans/2026-07-23-reliable-entity-extraction-maps.md were verified.
AUTO_EXTRACTED_ENTITY_TYPES = {"organization", "address", "person", "location"}

# Documents where an extracted address is very likely the user's own current
# address, not a third party's (e.g. a landlord on a rental contract, or a
# store on an invoice) -- residency detection only fires for these, contract
# documents get linked to the resulting residency period once it exists.
#
# "correspondence" and "other_documents" were added 2026-07-23 after live
# production data showed zero real documents were ever classified into the
# original four slugs, while both of these held genuine home-address
# extractions -- document_classification.py's classifier currently defaults
# to "other_documents" for 66% of all documents, so excluding it left this
# feature permanently dark. See
# docs/superpowers/specs/2026-07-23-reliable-entity-extraction-maps-design.md.
RESIDENCE_CATEGORY_SLUGS = {
    "identity_document", "mortgage_housing", "rental_contract", "government",
    "correspondence", "other_documents",
}
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
    # A phone number extracted as entity_type="address" is the same failure mode as
    # the email/URL/salutation cases above -- found 2026-07-23 verifying against a
    # real document, where the LLM extracted the same phone number both as a
    # person's "phone" field (correct) and as a standalone address entity. Only
    # rejects names with *no letters at all* that also parse as a phone number --
    # a real address always has letters (street/city), a bare phone number never
    # does, so this can't false-positive on e.g. "Achterweg 123, 9671 CT Winschoten"
    # just for containing several digits.
    stripped = name.strip()
    if stripped and not any(c.isalpha() for c in stripped) and parse_phone(stripped) is not None:
        return True
    return bool(_GARBAGE_ADDRESS_RE.search(name))

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


async def _find_matching_address_entity(db: AsyncSession, filled_item: dict, owner_id: UUID) -> Entity | None:
    """Priority-ordered partial match, most-reliable signal first. Returns the
    first entity found whose AddressDetail matches on the given fields -- both
    rows must have non-empty values for the fields being compared (an empty
    field never counts as a match)."""
    postal = (filled_item.get("postal_code") or "").strip().lower()
    house = (filled_item.get("house_number") or "").strip().lower()
    street = (filled_item.get("street") or "").strip().lower()

    if postal and house:
        result = await db.execute(
            select(Entity).join(AddressDetail, AddressDetail.entity_id == Entity.id).where(
                func.lower(AddressDetail.postal_code) == postal,
                func.lower(AddressDetail.house_number) == house,
                Entity.owner_id == owner_id,
            )
        )
        entity = result.scalar_one_or_none()
        if entity is not None:
            return entity

    if street and house:
        result = await db.execute(
            select(Entity).join(AddressDetail, AddressDetail.entity_id == Entity.id).where(
                func.lower(AddressDetail.street) == street,
                func.lower(AddressDetail.house_number) == house,
                Entity.owner_id == owner_id,
            )
        )
        entity = result.scalar_one_or_none()
        if entity is not None:
            return entity

    normalized_key = _normalize_address_key(filled_item)
    result = await db.execute(
        select(Entity).join(AddressDetail, AddressDetail.entity_id == Entity.id).where(
            AddressDetail.normalized_key == normalized_key, Entity.owner_id == owner_id
        )
    )
    return result.scalar_one_or_none()


async def _get_or_create_address_entity(db: AsyncSession, item: dict, owner_id: UUID) -> Entity | None:
    """Same contract as `_get_or_create_entity`, but dedups address entities by
    structured-field matching (priority-ordered, see _find_matching_address_entity)
    instead of exact name match. On a partial match, fills any gap on the existing
    row from the new extraction rather than creating a fragment -- never overwrites
    an already-populated field. Rejects candidates that look like an email/URL/
    person-salutation before ever creating an Entity row."""
    raw_name = str(item.get("name") or "").strip()
    if _looks_like_garbage_address(raw_name):
        logger.info("entity_agent: rejected garbage address candidate %r", raw_name)
        return None

    parsed = parse_address(raw_name)
    filled_item = {
        "name": raw_name,
        "street": item.get("street") or parsed["street"],
        "house_number": item.get("house_number") or parsed["house_number"],
        "postal_code": item.get("postal_code") or parsed["postal_code"],
        "city": item.get("city") or parsed["city"],
        "country": item.get("country") or parsed["country"],
    }

    entity = await _find_matching_address_entity(db, filled_item, owner_id)
    if entity is not None:
        if entity.status == "rejected":
            return None
        detail = await db.get(AddressDetail, entity.id)
        if detail is not None:
            changed = False
            for field in ("street", "house_number", "postal_code", "city", "country"):
                if getattr(detail, field) is None and filled_item[field] is not None:
                    setattr(detail, field, filled_item[field])
                    changed = True
            if changed:
                detail.normalized_key = _normalize_address_key(filled_item)
        return entity

    normalized_key = _normalize_address_key(filled_item)
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

        await _add_mention_if_missing(db, entity_id=entity.id, document_id=document_id)
        if entity_type in ("person", "organization"):
            await _upsert_contact_detail(db, entity=entity, item=item, owner_id=user_id, document_id=document_id)

    existing_address_names = {e.name.strip().lower() for e in persisted if e.entity_type == "address"}
    for match in find_full_address_matches(text):
        if match.strip().lower() in existing_address_names:
            continue
        entity = await _get_or_create_address_entity(db, {"name": match}, user_id)
        if entity is None:
            continue
        existing_address_names.add(match.strip().lower())
        if entity.id not in {e.id for e in persisted}:
            persisted.append(entity)
            address_entity_ids.append(entity.id)
        await _add_mention_if_missing(db, entity_id=entity.id, document_id=document_id)

    if address_entity_ids:
        if category_slug in RESIDENCE_CATEGORY_SLUGS:
            # Ambiguous which address is the user's own if several were found
            # (e.g. landlord + property on one rental contract) -- take the
            # first, still `pending_review` so a human can correct it.
            await _update_residency(db, user_id=user_id, address_entity_id=address_entity_ids[0], document_id=document_id)
        else:
            logger.info(
                "entity_agent: address extracted from document %s (category=%r) did not "
                "trigger residency detection -- category not in RESIDENCE_CATEGORY_SLUGS",
                document_id, category_slug,
            )

    await _maybe_link_contract(db, document_id=document_id, user_id=user_id, category_slug=category_slug)

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

    await db.commit()
    for entity in persisted:
        await db.refresh(entity)
    return persisted
