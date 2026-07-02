# CollaBrains

Privacy-first AI knowledge platform. AI is the central orchestration layer;
users interact via Web, Admin, Signal (chat-first), and later Mobile.

## Status: Phase 0 — project scaffold

See `docs/adr/0001-phase0-architecture.md` for the architecture decisions
behind this scaffold, and the phase plan below for what's next.

## Repo layout

- `apps/` — user-facing clients (web, admin, mobile, signal-bot)
- `services/` — backend services (api, auth, documents, entities, workflow,
  search, notifications, ai-gateway, ai-orchestrator)
- `agents/` — specialised AI agents (document, legal, planner, entity,
  communication, search)
- `packages/` — shared code (shared, types, ui, sdk, config)
- `infra/` — infrastructure config (postgres init scripts, etc.)
- `docs/adr/` — architecture decision records

Only `services/api` and `apps/web` have working code in Phase 0. Everything
else is scaffolded with a README stub and gets built out phase by phase.

## Local development

```bash
cp .env.example .env
docker compose up -d postgres redis
docker compose up api web
```

Full stack (adds Elasticsearch, Ollama, Paperless-ngx):

```bash
docker compose --profile full up
```

## Phases

0. Project setup (this) — monorepo, Docker Compose, FastAPI health, React shell
1. Core backend & document pipeline — LDAP auth, OCR, RAG, embeddings, search
2. AI orchestration & agents — AI Gateway, Orchestrator, first agents, workflow engine
3. Signal bot & communication — real Signal integration, proactive notifications
4. Case intelligence & entity graph
5. Frontend integration — full UI, chat, graph view, real-time updates
6. Production readiness — load testing, hardening, monitoring
