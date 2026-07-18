"""Document ingestion pipeline, summarization, and hybrid search.

Upload flow: bytes are forwarded straight to Paperless-ngx for OCR (no
intermediate disk write here -- Paperless owns file storage). The upload
endpoint only persists the `Document` row and publishes `DocumentUploaded`
(ADR 0017, Phase 8a) -- OCR, chunking/embedding, task/entity extraction, and
owner notification are event handlers reacting to that event and the ones it
chains into (`OCRCompleted` -> `EmbeddingsCreated` -> `TasksCreated` /
`EntitiesExtracted` / `VehiclesDetected` -> `NotificationRequested` ->
`WorkflowCompleted`), not
functions called directly from the endpoint. See
docs/adr/0004-phase2b-legal-planner-workflow.md and
docs/adr/0007-phase3c-signal-attachments-notifications.md for why each step
exists, and docs/adr/0017-phase8a-event-bus.md for why they're wired via the
event bus now instead of one sequential function. See
docs/adr/0002-phase1b-document-pipeline.md for why Paperless, Ollama, and
Postgres-native search (not Elasticsearch) were chosen, and
docs/adr/0003-phase2a-ai-gateway-orchestrator.md for the Document Agent
(summarization) and Search Agent (hybrid_search, in search_service.py).
Uploads are authenticated via `get_effective_user` (ADR 0006) so Signal
attachment uploads (ADR 0007) work the same way `/chat` does.

`_generate_summary` (the Document Agent's actual summarization call) is a
plain function, not inlined in the endpoint, so the Planning Engine
(Phase 8c, ADR 0019) can call the same code the HTTP endpoint does.
"""
import csv
import io
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.auth import get_effective_user
from api.cases import is_case_member
from api.chunking import chunk_text
from api.config import settings
from api.db import async_session, get_db
from api.document_classification import classify_and_persist
from api.embeddings import embed_text
from api.entity_agent import extract_entities
from api.events import Event, EventType, publish, subscribe
from api.models import Document, DocumentChunk, User
from api.paperless_client import delete_document as paperless_delete, fetch_document_file, \
    fetch_document_text, submit_document, wait_for_paperless_id
from api.planner_agent import extract_tasks
from api.search_service import hybrid_search
from api.signal_client import send_signal_message
from api.user_facts import extract_facts_from_document
from api.vehicle_agent import detect_and_link_vehicles

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentOut(BaseModel):
    id: UUID
    title: str
    filename: str
    mime_type: str
    status: str
    error: str | None
    doc_type: str | None
    tags: list[str]
    correspondent: str | None
    created_at: datetime
    processed_at: datetime | None


class DocumentDetailOut(DocumentOut):
    ocr_text: str | None
    chunk_count: int
    summary: str | None


async def _notify_owner(db: AsyncSession, document: Document) -> None:
    owner = await db.get(User, document.owner_id)
    if owner is None or not owner.phone_number:
        return
    if document.status == "ready":
        text = f'Your document "{document.title}" has finished processing and is ready to search.'
    else:
        text = f'Your document "{document.title}" failed to process. Check the CollaBrains app for details.'
    await send_signal_message(owner.phone_number, text)


@subscribe(EventType.DOCUMENT_UPLOADED)
async def _handle_document_uploaded(event: Event) -> None:
    document_id: UUID = event.payload["document_id"]
    filename: str = event.payload["filename"]
    mime_type: str = event.payload["mime_type"]
    content: bytes = event.payload["content"]

    await publish(EventType.WORKFLOW_STARTED, {"document_id": document_id})

    async with async_session() as db:
        document = await db.get(Document, document_id)
        if document is None:
            return
        try:
            document.status = "ocr_processing"
            await db.commit()

            task_id = await submit_document(filename, content, mime_type)
            paperless_id = await wait_for_paperless_id(task_id)
            text = await fetch_document_text(paperless_id)

            document.paperless_id = paperless_id
            document.ocr_text = text
            document.status = "embedding"
            await db.commit()
            await publish(EventType.OCR_COMPLETED, {"document_id": document_id, "text_length": len(text)})

            chunk_count = 0
            for chunk_count, chunk in enumerate(chunk_text(text), start=1):
                vector = await embed_text(chunk)
                db.add(
                    DocumentChunk(
                        document_id=document.id, chunk_index=chunk_count - 1, content=chunk, embedding=vector
                    )
                )

            document.status = "ready"
            document.processed_at = datetime.now(timezone.utc)
            await db.commit()

            await publish(
                EventType.EMBEDDINGS_CREATED,
                {
                    "document_id": document_id,
                    "owner_id": document.owner_id,
                    "text": text,
                    "chunk_count": chunk_count,
                },
            )
            await publish(EventType.NOTIFICATION_REQUESTED, {"document_id": document_id, "outcome": "ready"})
            await publish(EventType.WORKFLOW_COMPLETED, {"document_id": document_id, "outcome": "ready"})
        except Exception as exc:  # noqa: BLE001 - pipeline must never crash the worker
            document.status = "failed"
            document.error = str(exc)[:2000]
            await db.commit()
            await publish(EventType.NOTIFICATION_REQUESTED, {"document_id": document_id, "outcome": "failed"})
            await publish(EventType.WORKFLOW_COMPLETED, {"document_id": document_id, "outcome": "failed"})


@subscribe(EventType.DOCUMENT_REPROCESS_REQUESTED)
async def _handle_document_reprocess_requested(event: Event) -> None:
    """Admin-triggered retry (Phase 25) for a document stuck or failed after
    upload. Paperless already has the original bytes (`paperless_id`), so
    this re-fetches OCR text and replays the same tail of the pipeline
    `_handle_document_uploaded` runs after `wait_for_paperless_id` --
    re-chunking/embedding and re-publishing EMBEDDINGS_CREATED so entity
    extraction, task extraction, classification, etc. all re-run against the
    fresh text too, same as a first-time upload."""
    document_id: UUID = event.payload["document_id"]

    async with async_session() as db:
        document = await db.get(Document, document_id)
        if document is None or document.paperless_id is None:
            return
        try:
            document.status = "embedding"
            document.error = None
            await db.commit()

            text = await fetch_document_text(document.paperless_id)
            document.ocr_text = text
            await db.commit()
            await publish(EventType.OCR_COMPLETED, {"document_id": document_id, "text_length": len(text)})

            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

            chunk_count = 0
            for chunk_count, chunk in enumerate(chunk_text(text), start=1):
                vector = await embed_text(chunk)
                db.add(
                    DocumentChunk(
                        document_id=document.id, chunk_index=chunk_count - 1, content=chunk, embedding=vector
                    )
                )

            document.status = "ready"
            document.processed_at = datetime.now(timezone.utc)
            await db.commit()

            await publish(
                EventType.EMBEDDINGS_CREATED,
                {
                    "document_id": document_id,
                    "owner_id": document.owner_id,
                    "text": text,
                    "chunk_count": chunk_count,
                },
            )
            await publish(EventType.NOTIFICATION_REQUESTED, {"document_id": document_id, "outcome": "ready"})
            await publish(EventType.WORKFLOW_COMPLETED, {"document_id": document_id, "outcome": "ready"})
        except Exception as exc:  # noqa: BLE001 - pipeline must never crash the worker
            document.status = "failed"
            document.error = str(exc)[:2000]
            await db.commit()
            await publish(EventType.NOTIFICATION_REQUESTED, {"document_id": document_id, "outcome": "failed"})
            await publish(EventType.WORKFLOW_COMPLETED, {"document_id": document_id, "outcome": "failed"})


@subscribe(EventType.EMBEDDINGS_CREATED)
async def _handle_extract_tasks(event: Event) -> None:
    if not settings.auto_extract_tasks_on_ready:
        return
    document_id = event.payload["document_id"]
    async with async_session() as db:
        tasks = await extract_tasks(
            db,
            document_id=document_id,
            text=event.payload["text"],
            user_id=event.payload["owner_id"],
            source="planner_agent",
        )
    await publish(EventType.TASKS_CREATED, {"document_id": document_id, "task_count": len(tasks)})


@subscribe(EventType.EMBEDDINGS_CREATED)
async def _handle_extract_entities(event: Event) -> None:
    if not settings.auto_extract_entities_on_ready:
        return
    document_id = event.payload["document_id"]
    async with async_session() as db:
        entities = await extract_entities(
            db, document_id=document_id, text=event.payload["text"], user_id=event.payload["owner_id"]
        )
    await publish(EventType.ENTITIES_EXTRACTED, {"document_id": document_id, "entity_count": len(entities)})


@subscribe(EventType.EMBEDDINGS_CREATED)
async def _handle_extract_vehicles(event: Event) -> None:
    if not settings.auto_extract_vehicles_on_ready:
        return
    document_id = event.payload["document_id"]
    async with async_session() as db:
        vehicles = await detect_and_link_vehicles(
            db, document_id=document_id, text=event.payload["text"], owner_id=event.payload["owner_id"]
        )
    await publish(EventType.VEHICLES_DETECTED, {"document_id": document_id, "vehicle_count": len(vehicles)})


@subscribe(EventType.EMBEDDINGS_CREATED)
async def _handle_classify_document(event: Event) -> None:
    if not settings.auto_classify_on_ready:
        return
    document_id = event.payload["document_id"]
    async with async_session() as db:
        document = await classify_and_persist(
            db, document_id=document_id, text=event.payload["text"], user_id=event.payload["owner_id"]
        )
    if document is not None and document.doc_type is not None:
        await publish(EventType.DOCUMENT_CLASSIFIED, {"document_id": document_id, "doc_type": document.doc_type})


@subscribe(EventType.EMBEDDINGS_CREATED)
async def _handle_extract_facts(event: Event) -> None:
    if not settings.auto_extract_facts_on_ready:
        return
    document_id = event.payload["document_id"]
    async with async_session() as db:
        facts = await extract_facts_from_document(
            db, document_id=document_id, text=event.payload["text"], user_id=event.payload["owner_id"]
        )
    await publish(EventType.FACTS_EXTRACTED, {"document_id": document_id, "fact_count": len(facts)})


@subscribe(EventType.NOTIFICATION_REQUESTED)
async def _handle_notification_requested(event: Event) -> None:
    document_id = event.payload["document_id"]
    async with async_session() as db:
        document = await db.get(Document, document_id)
        if document is not None:
            await _notify_owner(db, document)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> Document:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    document = Document(
        owner_id=current_user.id,
        title=file.filename or "untitled",
        filename=file.filename or "untitled",
        mime_type=file.content_type or "application/octet-stream",
        status="pending",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    background_tasks.add_task(
        publish,
        EventType.DOCUMENT_UPLOADED,
        {
            "document_id": document.id,
            "filename": document.filename,
            "mime_type": document.mime_type,
            "content": content,
        },
    )
    return document


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> list[Document]:
    query = select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    if current_user.role != "admin":
        query = query.where(Document.owner_id == current_user.id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/export.csv")
async def export_documents_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> Response:
    query = select(Document).order_by(Document.created_at.desc())
    if current_user.role != "admin":
        query = query.where(Document.owner_id == current_user.id)
    result = await db.execute(query)
    documents = result.scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "title", "filename", "status", "doc_type", "correspondent", "tags", "created_at", "processed_at"])
    for document in documents:
        writer.writerow(
            [
                str(document.id),
                document.title,
                document.filename,
                document.status,
                document.doc_type or "",
                document.correspondent or "",
                ", ".join(document.tags or []),
                document.created_at.isoformat(),
                document.processed_at.isoformat() if document.processed_at else "",
            ]
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="documents.csv"'},
    )


async def _can_read_document(db: AsyncSession, document: Document, current_user: User) -> bool:
    """Owner and admin always can; an accepted member of the document's
    case can too (case-member document sharing, Phase 1) -- delete stays
    owner/admin-only, this only widens read/download access."""
    if document.owner_id == current_user.id or current_user.role == "admin":
        return True
    if document.case_id is not None:
        return await is_case_member(db, case_id=document.case_id, user_id=current_user.id)
    return False


@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> DocumentDetailOut:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not await _can_read_document(db, document, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this document")

    count_result = await db.execute(
        select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    return DocumentDetailOut(
        id=document.id,
        title=document.title,
        filename=document.filename,
        mime_type=document.mime_type,
        status=document.status,
        error=document.error,
        doc_type=document.doc_type,
        tags=document.tags,
        correspondent=document.correspondent,
        created_at=document.created_at,
        processed_at=document.processed_at,
        ocr_text=document.ocr_text,
        chunk_count=count_result.scalar_one(),
        summary=document.summary,
    )


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: UUID,
    disposition: str = Query("attachment"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> Response:
    if disposition not in ("attachment", "inline"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="disposition must be 'attachment' or 'inline'"
        )

    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not await _can_read_document(db, document, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this document")
    if document.paperless_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file not yet available")

    content, content_type = await fetch_document_file(document.paperless_id)
    # Filenames come from the original upload (UploadFile.filename) and are
    # attacker-controlled; strip control chars and quotes before they land
    # in a header value.
    safe_filename = "".join(ch for ch in document.filename if ch.isprintable() and ch not in '"\\').strip()
    safe_filename = safe_filename or "document"
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'{disposition}; filename="{safe_filename}"'},
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> None:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this document")

    if document.paperless_id is not None:
        await paperless_delete(document.paperless_id)

    await db.delete(document)
    await db.commit()


class SummaryOut(BaseModel):
    summary: str


SUMMARY_PROMPT = (
    "Summarize the following document in 3-5 sentences. Be factual and concise, "
    "and do not add information that isn't in the text.\n\nDocument:\n{text}"
)


async def _generate_summary(db: AsyncSession, document: Document, *, user_id: UUID, force: bool = False) -> str:
    """Compute (or return the cached) summary for an already-`ready` document.

    Callers (the HTTP endpoint, the Planning Engine's Document Agent step)
    are responsible for checking `document.status`/`document.ocr_text`
    first -- this assumes the document is ready.
    """
    if document.summary and not force:
        return document.summary

    prompt = SUMMARY_PROMPT.format(text=document.ocr_text[:8000])
    summary = await chat_completion(
        [{"role": "user", "content": prompt}],
        user_id=user_id,
        endpoint="documents.summarize",
    )

    document.summary = summary
    await db.commit()
    await publish(EventType.SUMMARY_CREATED, {"document_id": document.id, "summary_length": len(summary)})
    return summary


@router.post("/{document_id}/summarize", response_model=SummaryOut)
async def summarize_document(
    document_id: UUID,
    force: bool = Query(False, description="Regenerate even if a summary is already cached"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> SummaryOut:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.status != "ready" or not document.ocr_text:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Document is not ready yet (status: {document.status})"
        )

    summary = await _generate_summary(db, document, user_id=current_user.id, force=force)
    return SummaryOut(summary=summary)


class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str
    score: float


search_router = APIRouter(tags=["search"])


@search_router.get("/search", response_model=list[SearchResult])
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> list[SearchResult]:
    hits = await hybrid_search(db, q, limit=limit, owner_id=current_user.id)
    if not hits:
        return []

    document_ids = {hit.chunk.document_id for hit in hits}
    documents_result = await db.execute(select(Document).where(Document.id.in_(document_ids)))
    titles = {doc.id: doc.title for doc in documents_result.scalars().all()}

    return [
        SearchResult(
            chunk_id=hit.chunk.id,
            document_id=hit.chunk.document_id,
            document_title=titles.get(hit.chunk.document_id, ""),
            content=hit.chunk.content,
            score=hit.score,
        )
        for hit in hits
    ]
