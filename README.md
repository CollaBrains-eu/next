# CollaBrains

Privacy-first AI knowledge platform. AI is the central orchestration layer;
users interact via Web, Admin, Signal (chat-first), and later Mobile.

## Status: Phase 1b — document pipeline, embeddings, search

See `docs/adr/0001-phase0-architecture.md` and
`docs/adr/0002-phase1b-document-pipeline.md` for the architecture decisions
behind this build, and the phase plan below for what's next.

## Repo layout

- `apps/` — user-facing clients (web, admin, mobile, signal-bot)
- `services/` — backend services (api, auth, documents, entities, workflow,
  search, notifications, ai-gateway, ai-orchestrator)
- `agents/` — specialised AI agents (document, legal, planner, entity,
  communication, search)
- `packages/` — shared code (shared, types, ui, sdk, config)
- `infra/` — infrastructure config (postgres init scripts, LDAP test server)
- `docs/adr/` — architecture decision records

Only `services/api` and `apps/web` have working code so far. Everything
else is scaffolded with a README stub and gets built out phase by phase.

`services/api` covers LDAP auth + Postgres authorization (Phase 1a) and the
document pipeline: upload, OCR via Paperless-ngx, chunking, embeddings via
Ollama (`nomic-embed-text`), and hybrid (keyword + semantic) search over
Postgres/pgvector (Phase 1b). Elasticsearch is defined in Compose but
unused by the API — this host's OpenVZ container can't raise
`vm.max_map_count`, which Elasticsearch 8.x requires to boot. See ADR 0002.

## Local development

```bash
cp .env.example .env
docker compose up -d postgres redis openldap
docker compose up api web
```

Full stack (adds Elasticsearch, Ollama, Paperless-ngx):

```bash
docker compose --profile full up
```

## Phases

0. Project setup — monorepo, Docker Compose, FastAPI health, React shell (done)
1. Core backend & document pipeline (done) — split into:
   - 1a: LDAP auth + Postgres-backed authorization
   - 1b: document upload, OCR, chunking, embeddings, hybrid search
2. AI orchestration & agents — AI Gateway, Orchestrator, first agents, workflow engine
3. Signal bot & communication — real Signal integration, proactive notifications
4. Case intelligence & entity graph
5. Frontend integration — full UI, chat, graph view, real-time updates
6. Production readiness — load testing, hardening, monitoring
