# entity-agent

Entity extraction and relationship detection agent. Phase 4.

Implemented inside `services/api` (`api/entity_agent.py`,
`POST /documents/{id}/extract-entities`, `GET /entities`,
`GET /entities/{id}/graph`). Extracts people/organizations/locations and
typed relationships between them from a document's text, deduplicated by
exact case-insensitive name+type match (no fuzzy/LLM-based entity
resolution yet). See `docs/adr/0008-phase4-entity-graph.md`.
