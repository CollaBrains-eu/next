"""Registers existing agent capabilities as tools (Phase 9a, ADR 0021).

No new capability logic lives here -- each handler is a thin wrapper
converting primitive/JSON-friendly input to what the underlying
function (already exercised by its own endpoint's tests) needs, and its
output back to a plain dict. See ADR 0021 for why these five and not
more, and why a new tool doesn't require touching this file's siblings.
"""
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.documents import _generate_summary
from api.entity_agent import extract_entities
from api.legal import _generate_draft
from api.models import Document
from api.planner_agent import extract_tasks
from api.search_service import hybrid_search
from api.tool_registry import ToolDescriptor, register_tool
from api.vehicle_agent import lookup_vehicle as _lookup_vehicle


async def _search_handler(
    *, db: AsyncSession, user_id: UUID, query: str, limit: int = 10,
    document_ids: list[UUID] | None = None,
) -> dict[str, Any]:
    scope = set(document_ids) if document_ids else None
    hits = await hybrid_search(db, query, limit=limit, document_ids=scope)
    return {
        "documents": [
            {
                "chunk_id": str(hit.chunk.id),
                "document_id": str(hit.chunk.document_id),
                "content": hit.chunk.content,
                "score": hit.score,
            }
            for hit in hits
        ]
    }


async def _summarize_document_handler(
    *, db: AsyncSession, user_id: UUID, document_id: UUID, force: bool = False,
) -> dict[str, Any]:
    document = await db.get(Document, document_id)
    if document is None:
        raise ValueError(f"document not found: {document_id}")
    if document.status != "ready" or not document.ocr_text:
        raise ValueError(f"document is not ready yet (status: {document.status})")
    summary = await _generate_summary(db, document, user_id=user_id, force=force)
    return {"summary": summary}


async def _draft_legal_document_handler(
    *, db: AsyncSession, user_id: UUID, instruction: str,
    document_ids: list[UUID] | None = None, context_chunks: int = 8,
) -> dict[str, Any]:
    draft = await _generate_draft(
        db, instruction=instruction, user_id=user_id, document_ids=document_ids,
        context_chunks=context_chunks,
    )
    return draft.model_dump(mode="json")


async def _extract_tasks_handler(
    *, db: AsyncSession, user_id: UUID, document_id: UUID, text: str,
) -> dict[str, Any]:
    tasks = await extract_tasks(db, document_id=document_id, text=text, user_id=user_id, source="tool_registry")
    return {
        "tasks": [
            {"id": str(task.id), "title": task.title, "due_date": str(task.due_date) if task.due_date else None}
            for task in tasks
        ]
    }


async def _extract_entities_handler(
    *, db: AsyncSession, user_id: UUID, document_id: UUID, text: str,
) -> dict[str, Any]:
    entities = await extract_entities(db, document_id=document_id, text=text, user_id=user_id)
    return {
        "entities": [{"id": str(entity.id), "name": entity.name, "entity_type": entity.entity_type} for entity in entities]
    }


async def _lookup_vehicle_handler(*, db: AsyncSession, user_id: UUID, kenteken: str) -> dict[str, Any]:
    vehicle = await _lookup_vehicle(kenteken=kenteken)
    return {
        "kenteken": vehicle.kenteken,
        "merk": vehicle.merk,
        "handelsbenaming": vehicle.handelsbenaming,
        "voertuigsoort": vehicle.voertuigsoort,
        "eerste_kleur": vehicle.eerste_kleur,
        "datum_eerste_toelating": vehicle.datum_eerste_toelating,
        "vervaldatum_apk": vehicle.vervaldatum_apk,
        "wam_verzekerd": vehicle.wam_verzekerd,
        "openstaande_terugroepactie_indicator": vehicle.openstaande_terugroepactie_indicator,
        "brandstofomschrijving": vehicle.brandstofomschrijving,
        "found": vehicle.merk is not None,
    }


register_tool(ToolDescriptor(
    name="search",
    description="Search indexed documents by keyword and semantic similarity.",
    permissions=["documents.read"],
    input_schema={
        "query": "string",
        "limit": "integer (optional, default 10)",
        "document_ids": "array of string UUIDs (optional, restricts search scope)",
    },
    output_schema={"documents": "array of {chunk_id, document_id, content, score}"},
    handler=_search_handler,
))

register_tool(ToolDescriptor(
    name="summarize_document",
    description="Summarize a ready, OCR'd document in 3-5 sentences.",
    permissions=["documents.read"],
    input_schema={"document_id": "string UUID", "force": "boolean (optional, regenerate cached summary)"},
    output_schema={"summary": "string"},
    handler=_summarize_document_handler,
))

register_tool(ToolDescriptor(
    name="draft_legal_document",
    description="Draft a legal document grounded only in retrieved document context.",
    permissions=["legal.draft"],
    input_schema={
        "instruction": "string",
        "document_ids": "array of string UUIDs (optional, restricts context scope)",
        "context_chunks": "integer (optional, default 8)",
    },
    output_schema={"draft": "string", "citations": "array", "disclaimer": "string"},
    handler=_draft_legal_document_handler,
))

register_tool(ToolDescriptor(
    name="extract_tasks",
    description="Extract actionable tasks from document text via the Planner Agent.",
    permissions=["tasks.write"],
    input_schema={"document_id": "string UUID", "text": "string"},
    output_schema={"tasks": "array of {id, title, due_date}"},
    handler=_extract_tasks_handler,
))

register_tool(ToolDescriptor(
    name="extract_entities",
    description="Extract people/organizations/locations from document text via the Entity Agent.",
    permissions=["entities.write"],
    input_schema={"document_id": "string UUID", "text": "string"},
    output_schema={"entities": "array of {id, name, entity_type}"},
    handler=_extract_entities_handler,
))

register_tool(ToolDescriptor(
    name="lookup_vehicle",
    description="Look up a vehicle's RDW registration data by kenteken (Dutch license plate).",
    permissions=["vehicles.write"],
    input_schema={"kenteken": "string"},
    output_schema={
        "kenteken": "string", "merk": "string", "handelsbenaming": "string",
        "voertuigsoort": "string", "eerste_kleur": "string",
        "datum_eerste_toelating": "string", "vervaldatum_apk": "string",
        "wam_verzekerd": "string", "openstaande_terugroepactie_indicator": "string",
        "brandstofomschrijving": "string", "found": "boolean",
    },
    handler=_lookup_vehicle_handler,
))
