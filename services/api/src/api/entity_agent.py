"""Entity Agent: extract entities and relationships from a document's text.

See docs/adr/0008-phase4-entity-graph.md for scope: exact case-insensitive
name+type dedup only (no fuzzy/LLM-based entity resolution), relationships
only kept when both endpoints appear in the same extraction's entity list.
"""
import json
import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.models import Entity, EntityMention, EntityRelationship

logger = logging.getLogger(__name__)

VALID_ENTITY_TYPES = {"person", "organization", "location", "other"}

EXTRACTION_PROMPT = """Extract named entities and relationships between them from the \
following document. Return ONLY a JSON object (no prose, no markdown fences) with this shape:

{{"entities": [{{"name": str, "type": "person"|"organization"|"location"|"other"}}], \
"relationships": [{{"source": str, "target": str, "type": str}}]}}

"source" and "target" must exactly match a "name" from the entities list. If there are no \
entities, return {{"entities": [], "relationships": []}}.

Document:
{text}"""


async def _get_or_create_entity(db: AsyncSession, name: str, entity_type: str) -> Entity:
    result = await db.execute(
        select(Entity).where(func.lower(Entity.name) == name.lower().strip(), Entity.entity_type == entity_type)
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        entity = Entity(name=name.strip(), entity_type=entity_type)
        db.add(entity)
        await db.flush()
    return entity


async def extract_entities(db: AsyncSession, *, document_id: UUID, text: str, user_id: UUID) -> list[Entity]:
    """Extract entities/relationships from `text` via the AI Gateway and persist them."""
    prompt = EXTRACTION_PROMPT.format(text=text[:8000])
    raw = await chat_completion(
        [{"role": "user", "content": prompt}],
        user_id=user_id,
        endpoint="entity.extract",
        json_mode=True,
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

    entities_by_name: dict[str, Entity] = {}
    persisted: list[Entity] = []
    for item in raw_entities:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        entity_type = item.get("type") if item.get("type") in VALID_ENTITY_TYPES else "other"
        entity = await _get_or_create_entity(db, item["name"], entity_type)
        entities_by_name[item["name"].strip().lower()] = entity
        persisted.append(entity)

        existing = await db.execute(
            select(EntityMention).where(EntityMention.entity_id == entity.id, EntityMention.document_id == document_id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(EntityMention(entity_id=entity.id, document_id=document_id))

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
