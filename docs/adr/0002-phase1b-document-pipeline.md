# 0002: Phase 1b — Document Pipeline, Embeddings, and Search

## Status
Accepted (2026-07-02)

## Context
Phase 1b needs to take an uploaded file to searchable, retrievable text:
OCR/text extraction, chunking, embeddings, and a search API. The original
brief named Elasticsearch (keyword search) and Paperless-ngx (OCR) as stack
components. Both were feasibility-tested directly against the target host
(a resource-limited OpenVZ container, no GPU) before committing to an
implementation.

## Decisions

### OCR / document intake: Paperless-ngx (confirmed working)
Paperless-ngx starts cleanly under `--profile full`, becomes `healthy`, and
its REST API responds correctly to HTTP Basic auth using the admin
credentials already in `.env`. No separate Gotenberg/Tika services are
needed for the plain-text/PDF/image cases we target first — Paperless's
bundled OCRmyPDF/Tesseract handles those. OCR languages set to
`eng+nld+deu` (English/Dutch/German), with `PAPERLESS_OCR_LANGUAGES: nld deu`
so the extra Tesseract language packs auto-install on first boot (the
default image ships English only).

Flow: the API forwards the uploaded file's bytes directly to Paperless's
`POST /api/documents/post_document/` (no intermediate disk write in the API
container — Paperless owns file storage in its own media volume). The API
polls Paperless's task-status endpoint in a background task until the
document is consumed, then fetches the extracted text via
`GET /api/documents/{id}/`.

No task queue (Celery/RQ) is introduced in `services/api` for this — a
single in-process `asyncio` background task per upload is enough at this
stage's scale and keeps the stack from growing another moving part. This
should be revisited if upload volume or worker-restart durability becomes a
real requirement.

### Keyword/full-text search: Postgres `tsvector`, NOT Elasticsearch
Elasticsearch 8.x hard-requires `vm.max_map_count >= 262144` and refuses to
boot otherwise. This host's OpenVZ container has it locked at `65530` with
`sysctl -w` returning `Operation not permitted` — this is a host/hypervisor
-level setting an OpenVZ guest cannot change itself. This is a hard
blocker, not a configuration issue, confirmed by direct test before any
code was written.

Postgres already gives us most of what Elasticsearch would here: a
`tsvector` generated column with a GIN index for keyword ranking
(`ts_rank`), combined with pgvector for semantic search (see below) via
reciprocal rank fusion. This avoids a second search engine, a second index
to keep in sync, and the exact class of infra risk that cost significant
time on the OpenLDAP container earlier in Phase 1a. If a customer later
needs Elasticsearch-grade relevance features, it can be reintroduced behind
the existing `full` Compose profile on a host that supports the sysctl —
the document/chunk schema doesn't need to change for that.

### Embeddings: Ollama `nomic-embed-text` (768-dim)
Confirmed working: pulls and serves in seconds on CPU, no GPU needed.
768-dim output verified directly against `/api/embeddings`. Well-suited to
this host's 8 vCPU / 24GB RAM / no-GPU profile — a large embedding model
would make ingestion painfully slow with no compensating quality need at
this stage.

### Chunking
Fixed-size chunking (~800 characters, ~100 character overlap) over the
OCR'd plain text. No semantic/structure-aware chunking yet — simplest thing
that lets retrieval work; revisit if retrieval quality demands it once
real documents are in the system.

### Schema
`documents` (id, owner_id → users, title, filename, mime_type, paperless_id,
status, ocr_text, created_at, processed_at) and `document_chunks` (id,
document_id, chunk_index, content, embedding vector(768), content_tsv
generated tsvector column). `status` moves
`pending → ocr_processing → embedding → ready` (or `failed`) so the API can
report progress on `GET /documents/{id}` without polling Paperless directly
from the client.

### Search API
Single `GET /search?q=` endpoint doing both a pgvector cosine-distance
query (embed the query via the same Ollama model) and a `tsvector` keyword
query, merged via reciprocal rank fusion, returning chunk + parent-document
metadata. No separate `/search/keyword` vs `/search/semantic` split for
now — one hybrid endpoint is what the UI actually needs.
