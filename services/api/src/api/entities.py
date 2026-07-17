"""Entity extraction and graph query endpoints. See ADR 0008."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_effective_user
from api.db import get_db
from api.entity_agent import VALID_ENTITY_TYPES, extract_entities
from api.models import Document, Entity, EntityMention, EntityMergeLog, EntityRelationship, User

# Types a user can pick when manually creating an entity -- "other" is an auto-extraction
# fallback bucket, not a meaningful manual choice, and vehicles have their own dedicated
# creation flow (kenteken lookup in Vehicles.tsx), so both are excluded here.
MANUALLY_CREATABLE_ENTITY_TYPES = VALID_ENTITY_TYPES - {"other", "vehicle"}

router = APIRouter(tags=["entities"])


class EntityOut(BaseModel):
    id: UUID
    name: str
    entity_type: str
    status: str
    created_at: datetime


@router.post("/documents/{document_id}/extract-entities", response_model=list[EntityOut])
async def extract_entities_from_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> list[Entity]:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.status != "ready" or not document.ocr_text:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Document is not ready yet (status: {document.status})"
        )

    return await extract_entities(db, document_id=document.id, text=document.ocr_text, user_id=current_user.id)


@router.get("/entities", response_model=list[EntityOut])
async def list_entities(
    q: str | None = Query(None, description="Filter by name (case-insensitive substring)"),
    entity_type: str | None = Query(None),
    status: str = Query("confirmed", description="pending_review | confirmed | rejected | all"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> list[Entity]:
    query = select(Entity).order_by(Entity.name).limit(limit).offset(offset)
    if q:
        query = query.where(Entity.name.ilike(f"%{q}%"))
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    if status != "all":
        query = query.where(Entity.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/entities/pending-review-count")
async def count_pending_review_entities(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> dict[str, int]:
    result = await db.execute(select(func.count()).select_from(Entity).where(Entity.status == "pending_review"))
    return {"count": result.scalar_one()}


class EntityCreate(BaseModel):
    name: str
    entity_type: str


@router.post("/entities", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
async def create_entity(
    payload: EntityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> Entity:
    """Manually create a person/organization/location/address entity.

    Person and location entities are no longer auto-extracted from documents (see
    entity_agent.AUTO_EXTRACTED_ENTITY_TYPES) -- this is now the only way to add them.
    A manually-created entity is trusted by definition, so it starts `confirmed`
    rather than `pending_review`.
    """
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name is required")
    if payload.entity_type not in MANUALLY_CREATABLE_ENTITY_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid entity type")

    existing = await db.execute(
        select(Entity).where(func.lower(Entity.name) == name.lower(), Entity.entity_type == payload.entity_type)
    )
    entity = existing.scalar_one_or_none()
    if entity is not None:
        if entity.status != "confirmed":
            entity.status = "confirmed"
            await db.commit()
            await db.refresh(entity)
        return entity

    entity = Entity(name=name, entity_type=payload.entity_type, status="confirmed")
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return entity


class BulkReviewItem(BaseModel):
    entity_id: UUID
    action: str  # "approve" | "reject"


async def _transition_entity(db: AsyncSession, entity_id: UUID, new_status: str) -> Entity:
    entity = await db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    if entity.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Entity is not pending review (status: {entity.status})",
        )
    entity.status = new_status
    await db.commit()
    await db.refresh(entity)
    return entity


@router.post("/entities/{entity_id}/approve", response_model=EntityOut)
async def approve_entity(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> Entity:
    return await _transition_entity(db, entity_id, "confirmed")


@router.post("/entities/{entity_id}/reject", response_model=EntityOut)
async def reject_entity(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> Entity:
    return await _transition_entity(db, entity_id, "rejected")


@router.post("/entities/bulk-review", response_model=list[EntityOut])
async def bulk_review_entities(
    items: list[BulkReviewItem],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> list[Entity]:
    results: list[Entity] = []
    for item in items:
        new_status = "confirmed" if item.action == "approve" else "rejected"
        results.append(await _transition_entity(db, item.entity_id, new_status))
    return results


class GraphNode(BaseModel):
    id: UUID
    name: str
    entity_type: str


class GraphEdge(BaseModel):
    source: UUID
    target: UUID
    relationship_type: str
    document_id: UUID | None


class EntityGraphOut(BaseModel):
    center: GraphNode
    nodes: list[GraphNode]
    edges: list[GraphEdge]


@router.get("/entities/{entity_id}/graph", response_model=EntityGraphOut)
async def get_entity_graph(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> EntityGraphOut:
    """One-hop neighborhood of an entity: itself, its direct confirmed neighbors, and the
    confirmed-to-confirmed edges between them. Non-confirmed neighbors/edges are excluded --
    see docs/superpowers/specs/2026-07-09-entity-review-queue-design.md."""
    center = await db.get(Entity, entity_id)
    if center is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    edges_result = await db.execute(
        select(EntityRelationship).where(
            or_(EntityRelationship.source_entity_id == entity_id, EntityRelationship.target_entity_id == entity_id)
        )
    )
    all_edges = list(edges_result.scalars().all())

    neighbor_ids = {
        eid
        for edge in all_edges
        for eid in (edge.source_entity_id, edge.target_entity_id)
        if eid != entity_id
    }
    neighbors: list[Entity] = []
    if neighbor_ids:
        neighbors_result = await db.execute(
            select(Entity).where(Entity.id.in_(neighbor_ids), Entity.status == "confirmed")
        )
        neighbors = list(neighbors_result.scalars().all())
    confirmed_neighbor_ids = {n.id for n in neighbors}

    edges = [
        edge
        for edge in all_edges
        for other_id in [edge.target_entity_id if edge.source_entity_id == entity_id else edge.source_entity_id]
        if other_id in confirmed_neighbor_ids
    ]

    return EntityGraphOut(
        center=GraphNode(id=center.id, name=center.name, entity_type=center.entity_type),
        nodes=[GraphNode(id=n.id, name=n.name, entity_type=n.entity_type) for n in neighbors],
        edges=[
            GraphEdge(
                source=edge.source_entity_id,
                target=edge.target_entity_id,
                relationship_type=edge.relationship_type,
                document_id=edge.document_id,
            )
            for edge in edges
        ],
    )


class MergeRequest(BaseModel):
    source_entity_id: UUID


async def merge_entities(db: AsyncSession, *, target_id: UUID, source_id: UUID, merged_by: UUID) -> Entity:
    """Merge `source_id` into `target_id`: move mentions/relationships, delete `source_id`.

    Migrated from CollaBrains v2's `POST /entities/{target_id}/merge` -- Next's automatic
    dedup only catches exact case-insensitive name+type matches (ADR 0008); this covers the
    cases that misses (e.g. "Acme Corp" vs "Acme Corporation").
    """
    target = await db.get(Entity, target_id)
    source = await db.get(Entity, source_id)
    if target is None or source is None:
        raise ValueError("target or source entity not found")

    existing_mentions = await db.execute(select(EntityMention.document_id).where(EntityMention.entity_id == target_id))
    existing_document_ids = {row[0] for row in existing_mentions.all()}

    mentions_result = await db.execute(select(EntityMention).where(EntityMention.entity_id == source_id))
    for mention in mentions_result.scalars().all():
        if mention.document_id in existing_document_ids:
            # Target already has a mention for this document -- moving would violate the
            # (entity_id, document_id) unique constraint. Leave it pointed at source_id;
            # deleting source below cascades it away (ON DELETE CASCADE) instead of an
            # explicit delete here racing with that same cascade.
            continue
        mention.entity_id = target_id
        existing_document_ids.add(mention.document_id)

    relationships_result = await db.execute(
        select(EntityRelationship).where(
            or_(EntityRelationship.source_entity_id == source_id, EntityRelationship.target_entity_id == source_id)
        )
    )
    for relationship in relationships_result.scalars().all():
        new_source = target_id if relationship.source_entity_id == source_id else relationship.source_entity_id
        new_target = target_id if relationship.target_entity_id == source_id else relationship.target_entity_id
        if new_source == new_target:
            # source and target already had a direct relationship to each other -- repointing
            # would create a meaningless self-loop. Leave it referencing source_id; deleting
            # source below cascades it away instead of an explicit delete racing that cascade.
            continue
        relationship.source_entity_id = new_source
        relationship.target_entity_id = new_target

    db.add(EntityMergeLog(source_entity_id=source_id, target_entity_id=target_id, merged_by=merged_by))
    await db.delete(source)
    await db.commit()
    await db.refresh(target)
    return target


@router.post("/entities/{target_id}/merge", response_model=EntityOut)
async def merge_entity(
    target_id: UUID,
    request: MergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> Entity:
    if target_id == request.source_entity_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot merge an entity into itself")
    try:
        return await merge_entities(
            db, target_id=target_id, source_id=request.source_entity_id, merged_by=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
