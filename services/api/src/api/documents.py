"""Document ingestion pipeline, summarization, and hybrid search.

Upload flow: bytes are forwarded straight to Paperless-ngx for OCR (no
intermediate disk write here -- Paperless owns file storage). A background
task polls Paperless until text is ready, then chunks and embeds it via
Ollama, then (if enabled) triggers the Planner Agent to extract tasks and
notifies the owner on Signal if they've linked a phone number -- the
workflow triggers from docs/adr/0004-phase2b-legal-planner-workflow.md and
docs/adr/0007-phase3c-signal-attachments-notifications.md. See
docs/adr/0002-phase1b-document-pipeline.md for why Paperless, Ollama, and
Postgres-native search (not Elasticsearch) were chosen, and
docs/adr/0003-phase2a-ai-gateway-orchestrator.md for the Document Agent
(summarization) and Search Agent (hybrid_search, in search_service.py).
Uploads are authenticated via `get_effective_user` (ADR 0006) so Signal
attachment uploads (ADR 0007) work the same way `/chat` does.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion
from api.auth import get_effective_user
from api.chunking import chunk_text
from api.config import settings
from api.db import async_session, get_db
from api.embeddings import embed_text
from api.models import Document, DocumentChunk, User
from api.paperless_client import delete_document as paperless_delete, fetch_document_text, \
    submit_document, wait_for_paperless_id
from api.planner_agent import extract_tasks
from api.search_service import hybrid_search
from api.signal_client import send_signal_message

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)


class DocumentOut(BaseModel):
    id: UUID
    title: str
    filename: str
    mime_type: str
    status: str
    error: str | None
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
    try:
        if document.status == "ready":
            text = f'Your document "{document.title}" has finished processing and is ready to search.'
        else:
            text = f'Your document "{document.title}" failed to process. Check the CollaBrains app for details.'
        await send_signal_message(owner.phone_number, text)
    except Exception:  # noqa: BLE001 - notification failure must never affect the pipeline
        logger.exception("failed to send Signal notification for document %s", document.id)


async def _process_document(document_id: UUID, filename: str, content: bytes, mime_type: str) -> None:
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

            for index, chunk in enumerate(chunk_text(text)):
                vector = await embed_text(chunk)
                db.add(DocumentChunk(document_id=document.id, chunk_index=index, content=chunk, embedding=vector))

            document.status = "ready"
            document.processed_at = datetime.now(timezone.utc)
            await db.commit()

            if settings.auto_extract_tasks_on_ready:
                try:
                    await extract_tasks(
                        db, document_id=document.id, text=text, user_id=document.owner_id, source="planner_agent"
                    )
                except Exception:  # noqa: BLE001 - the workflow trigger must never fail the ingest pipeline
                    logger.exception("auto task-extraction failed for document %s", document.id)

            await _notify_owner(db, document)
        except Exception as exc:  # noqa: BLE001 - pipeline must never crash the worker
            document.status = "failed"
            document.error = str(exc)[:2000]
            await db.commit()
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

    background_tasks.add_task(_process_document, document.id, document.filename, content, document.mime_type)
    return document


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> list[Document]:
    result = await db.execute(
        select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> DocumentDetailOut:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

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
        created_at=document.created_at,
        processed_at=document.processed_at,
        ocr_text=document.ocr_text,
        chunk_count=count_result.scalar_one(),
        summary=document.summary,
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

    if document.summary and not force:
        return SummaryOut(summary=document.summary)

    prompt = SUMMARY_PROMPT.format(text=document.ocr_text[:8000])
    summary = await chat_completion(
        [{"role": "user", "content": prompt}],
        user_id=current_user.id,
        endpoint="documents.summarize",
    )

    document.summary = summary
    await db.commit()
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
    hits = await hybrid_search(db, q, limit=limit)
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
