"""Document ingestion pipeline and hybrid search.

Upload flow: bytes are forwarded straight to Paperless-ngx for OCR (no
intermediate disk write here -- Paperless owns file storage). A background
task polls Paperless until text is ready, then chunks and embeds it via
Ollama. See docs/adr/0002-phase1b-document-pipeline.md for why Paperless,
Ollama, and Postgres-native search (not Elasticsearch) were chosen.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.chunking import chunk_text
from api.db import async_session, get_db
from api.embeddings import embed_text
from api.models import Document, DocumentChunk, User
from api.paperless_client import delete_document as paperless_delete, fetch_document_text, \
    submit_document, wait_for_paperless_id

router = APIRouter(prefix="/documents", tags=["documents"])


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
        except Exception as exc:  # noqa: BLE001 - pipeline must never crash the worker
            document.status = "failed"
            document.error = str(exc)[:2000]
            await db.commit()


@router.post("", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
) -> list[Document]:
    result = await db.execute(
        select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
) -> list[SearchResult]:
    candidate_pool = max(limit * 3, 20)
    rrf_k = 60

    query_vector = await embed_text(q)
    semantic_result = await db.execute(
        select(DocumentChunk)
        .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
        .limit(candidate_pool)
    )
    semantic_hits = list(semantic_result.scalars().all())

    tsquery = func.plainto_tsquery("english", q)
    keyword_result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.content_tsv.op("@@")(tsquery))
        .order_by(func.ts_rank(DocumentChunk.content_tsv, tsquery).desc())
        .limit(candidate_pool)
    )
    keyword_hits = list(keyword_result.scalars().all())

    scores: dict[UUID, float] = {}
    chunks_by_id: dict[UUID, DocumentChunk] = {}
    for rank_list in (semantic_hits, keyword_hits):
        for rank, chunk in enumerate(rank_list):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (rrf_k + rank + 1)
            chunks_by_id[chunk.id] = chunk

    ranked_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:limit]
    if not ranked_ids:
        return []

    documents_result = await db.execute(
        select(Document).where(Document.id.in_({chunks_by_id[cid].document_id for cid in ranked_ids}))
    )
    titles = {doc.id: doc.title for doc in documents_result.scalars().all()}

    return [
        SearchResult(
            chunk_id=cid,
            document_id=chunks_by_id[cid].document_id,
            document_title=titles.get(chunks_by_id[cid].document_id, ""),
            content=chunks_by_id[cid].content,
            score=scores[cid],
        )
        for cid in ranked_ids
    ]
