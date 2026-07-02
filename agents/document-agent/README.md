# document-agent

Document analysis agent. Phase 2a.

Implemented inside `services/api` (`api/documents.py`,
`POST /documents/{id}/summarize`). One capability so far — LLM
summarization, cached on `documents.summary`. See
`docs/adr/0003-phase2a-ai-gateway-orchestrator.md`.
