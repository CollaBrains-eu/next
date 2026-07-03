# CollaBrains

Privacy-first AI knowledge platform. AI is the central orchestration layer;
users interact via Web, Admin, Signal (chat-first), and later Mobile.

## Status: Phase 5a — Frontend auth & document library

See `docs/adr/` for the architecture decisions behind this build
(0001: scaffold, 0002: document pipeline, 0003: AI Gateway/Orchestrator,
0004: Legal/Planner agents + workflow, 0005: Signal bot, 0006: Signal
identity linking, 0007: Signal attachments & notifications, 0008: entity
graph, 0009: frontend auth & documents), and the phase plan below for
what's next. Phases 0-4 and 5a are done.

## Repo layout

- `apps/` — user-facing clients (web, admin, mobile, signal-bot)
- `services/` — backend services (api, auth, documents, entities, workflow,
  search, notifications, ai-gateway, ai-orchestrator)
- `agents/` — specialised AI agents (document, legal, planner, entity,
  communication, search)
- `packages/` — shared code (shared, types, ui, sdk, config)
- `infra/` — infrastructure config (postgres init scripts, LDAP test
  server, signal-cli registration data)
- `docs/adr/` — architecture decision records

`services/api`, `apps/web`, and `apps/signal-bot` have working code.
Everything else is scaffolded with a README stub and gets built out phase
by phase — including `services/ai-gateway`, `services/ai-orchestrator`,
and `services/workflow`, whose actual implementation currently lives
inside `services/api` (see ADR 0003 and ADR 0004).

`services/api` covers:

- **Phase 1a** — LDAP auth + Postgres-backed authorization.
- **Phase 1b** — document upload, OCR (Paperless-ngx), chunking, embeddings
  (Ollama `nomic-embed-text`), hybrid keyword+semantic search over
  Postgres/pgvector. Elasticsearch is defined in Compose but unused — this
  host's OpenVZ container can't raise `vm.max_map_count`, which
  Elasticsearch 8.x requires to boot. See ADR 0002.
- **Phase 2a** — an AI Gateway (`api/ai_gateway.py`: model calls, per-user
  rate limiting, audit log) fronting Ollama `qwen2.5:3b-instruct`; an
  Orchestrator (`POST /chat`) that answers questions grounded in retrieved
  document chunks with citations; a Document Agent
  (`POST /documents/{id}/summarize`); and a Search Agent
  (`api/search_service.hybrid_search`, shared by `/search` and `/chat`).
  See ADR 0003.
- **Phase 2b** — a Legal Agent (`POST /legal/draft`) that drafts documents
  grounded only in retrieved context, never inventing case law or citing
  facts not present in the source documents; a Planner Agent
  (`POST /documents/{id}/extract-tasks`, `GET /tasks`,
  `PATCH /tasks/{id}`) that extracts actionable items from document text;
  and a minimal in-process workflow trigger (document ready → auto
  task-extraction). See ADR 0004.

`apps/signal-bot` bridges Signal to `/chat`: polls
`signal-cli-rest-api` for incoming messages on the registered number
(`+4949534254784`), forwards them to the orchestrator, replies on Signal
(Phase 3a, ADR 0005). Each sender's phone number is resolved and matched
against `users.phone_number` — only senders who've linked their number
via `PUT /auth/me/phone` get answered, attributed to their own account for
rate limiting and audit (Phase 3b, ADR 0006). Sending the bot a file
uploads it into the same document pipeline as a web upload, and
`services/api` messages the owner back on Signal directly once processing
finishes — no polling, the bot just acknowledges receipt (Phase 3c, ADR
0007).

A Document Ready trigger also runs the Entity Agent
(`api/entity_agent.py`): extracts people/organizations/locations and
relationships between them via `qwen2.5:3b-instruct` in Ollama's
grammar-constrained JSON mode (needed — the model occasionally produces
malformed JSON on more complex extractions when only prompted to "return
JSON," a real failure caught in live testing), deduplicated by exact
case-insensitive name+type match. `GET /entities/{id}/graph` returns an
entity's one-hop neighborhood (itself, direct neighbors, edges) — the
shape a graph visualization (Phase 5c) needs (Phase 4, ADR 0008).

`apps/web` is now a real (not stub) React app: LDAP-backed login
(`POST /auth/token`, JWT in `localStorage`, `AuthContext` +
`ProtectedRoute` guarding all routes), a document library (list with
status badges, upload, delete, detail view with OCR text/summary,
keyword+semantic search), and a typed `src/lib/api.ts` client used by
every screen. AI Chat, Legal draft, and Task UI land in Phase 5b; the
entity graph visualization lands in Phase 5c (Phase 5a, ADR 0009).

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

Signal bot (needs a registered number, see ADR 0005):

```bash
docker compose --profile signal up -d
```

Frontend tests:

```bash
cd apps/web && pnpm test
```

## Phases

0. Project setup — monorepo, Docker Compose, FastAPI health, React shell (done)
1. Core backend & document pipeline (done) — split into:
   - 1a: LDAP auth + Postgres-backed authorization
   - 1b: document upload, OCR, chunking, embeddings, hybrid search
2. AI orchestration & agents (done) — split into:
   - 2a: AI Gateway, Orchestrator (RAG chat), Document Agent, Search Agent
   - 2b: Legal Agent, Planner Agent, workflow trigger
3. Signal bot & communication (done) — split into:
   - 3a (done): registration, text-chat bridge to /chat
   - 3b (done): per-sender identity mapping by linked phone number
   - 3c (done): document upload via Signal attachments, proactive
     notifications on document completion
4. Case intelligence & entity graph (done) — entity/relationship
   extraction (Entity Agent), one-hop graph query API. The visual graph
   view itself is Phase 5c scope.
5. Frontend integration — split into:
   - 5a (done): auth (login, JWT, protected routes), document library
     (list, upload, detail, search)
   - 5b: AI chat UI (citations, multi-turn history), Legal draft UI,
     Task list UI
   - 5c: entity graph visualization
6. Production readiness — load testing, hardening, monitoring
