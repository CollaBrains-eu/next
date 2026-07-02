# search-agent

Semantic and keyword search agent. Phase 1b / 2a.

Implemented inside `services/api` as `api/search_service.hybrid_search()`
— Postgres tsvector (keyword) + pgvector HNSW (semantic), merged via
reciprocal rank fusion. Used by both `GET /search` and the chat
orchestrator's retrieval step. See
`docs/adr/0002-phase1b-document-pipeline.md` and
`docs/adr/0003-phase2a-ai-gateway-orchestrator.md`.
