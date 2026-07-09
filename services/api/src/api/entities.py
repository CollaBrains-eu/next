"""Entity extraction and graph query endpoints. See ADR 0008."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_effective_user
from api.db import get_db
from api.entity_agent import extract_entities
from api.models import Document, Entity, EntityRelationship, User

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
    result = await db.execute(query)
    return list(result.scalars().all())


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
    """One-hop neighborhood of an entity: itself, its direct neighbors, and the edges between them."""
    center = await db.get(Entity, entity_id)
    if center is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    edges_result = await db.execute(
        select(EntityRelationship).where(
            or_(EntityRelationship.source_entity_id == entity_id, EntityRelationship.target_entity_id == entity_id)
        )
    )
    edges = list(edges_result.scalars().all())

    neighbor_ids = {
        eid
        for edge in edges
        for eid in (edge.source_entity_id, edge.target_entity_id)
        if eid != entity_id
    }
    neighbors: list[Entity] = []
    if neighbor_ids:
        neighbors_result = await db.execute(select(Entity).where(Entity.id.in_(neighbor_ids)))
        neighbors = list(neighbors_result.scalars().all())

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
