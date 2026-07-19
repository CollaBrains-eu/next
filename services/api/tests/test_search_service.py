from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import func, select, text

from api.db import async_session
from api.models import Document, DocumentChunk, User
from api.search_service import hybrid_search

FAKE_EMBEDDING = [0.1] * 768


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_document_with_chunk(owner_id, *, content: str, language: str) -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="t", filename="f.pdf", mime_type="application/pdf",
            status="ready", language=language,
        )
        db.add(document)
        await db.flush()
        chunk = DocumentChunk(document_id=document.id, chunk_index=0, content=content, embedding=FAKE_EMBEDDING)
        db.add(chunk)
        await db.flush()
        await db.execute(
            text("UPDATE document_chunks SET content_tsv = to_tsvector(:lang, content) WHERE id = :id"),
            {"lang": language, "id": chunk.id},
        )
        await db.commit()
        await db.refresh(document)
        return document


async def test_dutch_ts_config_stems_a_plural_the_english_config_misses():
    """The hypothesis this whole feature rests on, checked directly against
    Postgres: 'overeenkomsten' (agreements) and 'overeenkomst' (agreement)
    share a lexeme only under Dutch stemming rules -- English's stemmer
    doesn't know Dutch plural morphology and won't fold them together."""
    async with async_session() as db:
        dutch_match = (
            await db.execute(
                select(func.to_tsvector("dutch", "overeenkomsten").op("@@")(func.plainto_tsquery("dutch", "overeenkomst")))
            )
        ).scalar()
        english_match = (
            await db.execute(
                select(
                    func.to_tsvector("english", "overeenkomsten").op("@@")(func.plainto_tsquery("english", "overeenkomst"))
                )
            )
        ).scalar()

    assert dutch_match is True
    assert english_match is False


async def test_hybrid_search_ranks_correctly_stemmed_content_above_english_stemmed_content():
    """Isolates the storage-side half of the fix: two chunks with identical
    text and identical (faked) embeddings -- so semantic score contributes
    equally to both -- differing only in which config computed their
    content_tsv (this feature's fix vs. the pre-fix hardcoded 'english').
    Both are searched with the correct language for their content
    ('dutch'); only the chunk whose content_tsv was itself built with
    'dutch' should get the extra keyword-match score contribution."""
    user = await _create_user(_unique("searchlangdutch"))
    dutch_stored = await _create_document_with_chunk(
        user.id, content="De overeenkomsten zijn ondertekend.", language="dutch",
    )
    english_stored = await _create_document_with_chunk(
        user.id, content="De overeenkomsten zijn ondertekend.", language="english",
    )

    async with async_session() as db:
        with patch("api.search_service.embed_text", return_value=FAKE_EMBEDDING):
            hits = await hybrid_search(db, "overeenkomst", owner_id=user.id, language="dutch")

    scores_by_document = {hit.chunk.document_id: hit.score for hit in hits}
    assert scores_by_document[dutch_stored.id] > scores_by_document[english_stored.id]
