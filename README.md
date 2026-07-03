# CollaBrains

Privacy-first AI knowledge platform. AI is the central orchestration layer;
users interact via Web, Mobile, Signal (chat-first), and later Admin.

## Status: Phase 7 — Mobile App

See `docs/adr/` for the architecture decisions behind this build
(0001: scaffold, 0002: document pipeline, 0003: AI Gateway/Orchestrator,
0004: Legal/Planner agents + workflow, 0005: Signal bot, 0006: Signal
identity linking, 0007: Signal attachments & notifications, 0008: entity
graph, 0009: frontend auth & documents, 0010: chat/legal/tasks UI, 0011:
entity graph UI, 0012: TLS & reverse proxy, 0013: backups, 0014:
monitoring & alerting, 0015: load testing, 0016: mobile app foundation).
Phases 0-4, all of Phase 5 (5a, 5b, 5c), all of Phase 6 (6a, 6b, 6c, 6d),
and Phase 7 are done — every phase in both the original 7-phase plan and
the subsequent mobile phase.

The app is live at **https://v78281.1blu.de** (real Let's Encrypt
certificate, auto-renewing). `api` and the Vite dev server are no longer
reachable from the public internet — see "Production deployment" below.

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

`services/api`, `apps/web`, `apps/signal-bot`, and `apps/mobile` have
working code. Everything else (`apps/admin`) is scaffolded with a README
stub and gets built out phase by phase — including `services/ai-gateway`,
`services/ai-orchestrator`, and `services/workflow`, whose actual
implementation currently lives inside `services/api` (see ADR 0003 and
ADR 0004).

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

`apps/web` is a real (not stub) React app. Auth (LDAP login, JWT,
protected routes) and the document library (list, upload, delete, detail
view, keyword+semantic search) shipped in Phase 5a (ADR 0009). Phase 5b
(ADR 0010) adds: AI Chat (`/chat` route — full-history RAG chat with
inline citation links back to source documents), Legal Draft (`/legal`
route — one-shot grounded drafting scoped to selected documents, always
shows the attorney-review disclaimer), and Tasks (`/tasks` route — list
with open/done/all filter, checkbox toggle calling `PATCH /tasks/{id}`).
Phase 5c (ADR 0011) adds the entity graph explorer: a searchable/
type-filterable `/entities` list backed by `GET /entities`, and
`/entities/:id`, a hand-written SVG radial layout of that entity's
one-hop neighborhood (`GET /entities/{id}/graph`) — center node in the
middle, direct relationships arranged around it with labeled edges.
Clicking any neighbor node re-centers the graph on it, which is how
multi-hop exploration works given the backend only ever returns one hop
at a time (a deliberate Phase 4 design choice, not a limitation worked
around). No graph-layout library was added — for an always-small
hub-and-spoke shape, a circular placement is simpler than pulling in
d3-force or similar.

Phase 6a (ADR 0012) put a real TLS/reverse-proxy layer in front of
everything: Caddy terminates HTTPS for `v78281.1blu.de` (the
hosting-assigned hostname, already resolving here — automatic
Let's-Encrypt-issued cert, self-renewing, no certbot/cron needed), serves
the production frontend build as static files, and proxies known API
path prefixes to `api:8000` over the internal Docker network. `api` and
the Vite dev server's Compose port bindings were rebound to
`127.0.0.1` — the same fix already proven correct twice earlier in this
project (Postgres/Redis in Phase 0, Ollama/Paperless/Elasticsearch in
Phase 1b) for the same reason: Docker's own port-publishing writes
iptables rules UFW doesn't filter by default, so UFW rules alone weren't
actually blocking anything. UFW now only allows 22/80/443.

Phase 6b (ADR 0013) added automated daily backups (`infra/backup/backup.sh`,
root cron at 03:00, 14-day retention) of the three things on this host
that would be genuinely costly or impossible to reconstruct if lost:
Postgres (`pg_dump -Fc`), LDAP (`slapcat`), and the registered Signal
number's encryption/session keys (`infra/signal-cli/`, a plain tarball —
losing this means redoing Phase 3a's human-in-the-loop registration from
scratch). Backups live in `/opt/collabrains-backups/`, deliberately
outside the git working tree. All three were verified as genuinely
restorable via real round-trips, not just "a file got created" — see
`docs/runbooks/backup-restore.md`, which also documents a real bug found
while testing the LDAP restore: the container's normal bootstrap flow
seeds via `ldapadd` (an online LDAP operation) which silently rejects
the operational attributes a `slapcat` dump contains, so restoring that
way *looks* like it worked but restores nothing — the runbook's
procedure uses an offline `slapadd` instead.

Phase 6c (ADR 0014) added a health watchdog (`infra/monitoring/watchdog.sh`,
root cron every 5 minutes) — no new monitoring stack, just HTTP checks
against `/health`/`/health/ready` (both the internal `127.0.0.1:8000`
path and the public `https://v78281.1blu.de` path — deliberately both,
since a Caddy routing bug in Phase 6a's own testing would only ever have
shown up in the public-path check), every container's running state, and
disk usage. Alerts over Signal — reusing the bot from Phase 3 rather than
standing up a second notification channel — to whichever number is set
as `ALERT_PHONE_NUMBER` in `.env`, and only on healthy↔unhealthy
*transitions*, not every failed check, so an ongoing outage doesn't page
every 5 minutes for its duration. Verified with a real drill: stopped a
container, confirmed the down-alert actually reached signal-cli (`201`
from `POST /v2/send`, not just that the script attempted it), confirmed
no duplicate alert on a second unhealthy check, restarted the container,
and confirmed a distinct recovery alert fired. That drill also caught a
real bug in the first version of the container-state check: it derived
its "expected" service list from `docker compose ps --services` without
realizing this Compose version defaults that to *running* services only
— making the down-detection tautological, since a stopped container
would silently drop out of both the expected and running lists at once
and never be flagged. Fixed using `docker compose ps -a` (all states)
instead.

Phase 6d (ADR 0015) closed out Phase 6 with a real load test
(`infra/loadtest/loadtest.py`, no framework — a short `asyncio`+`httpx`
script) against `/chat` (LLM-bound) and `/search` (DB-only baseline) at
concurrency 1/2/4/8, using 8 disposable test users so the per-user rate
limiter didn't distort the results. Full numbers and analysis in
`docs/runbooks/capacity.md`; the short version: Postgres search stays
under a second even at 8 concurrent requests, but Ollama runs with
`OLLAMA_NUM_PARALLEL:1` on this host (confirmed directly in its startup
log, never explicitly configured either way) — generation requests
fully serialize, and `docker stats` showed Ollama alone using 752% of
this 8-vCPU host's CPU during the concurrency=8 run. Practical guidance:
comfortable up to ~2 people using chat/legal-draft at the same moment,
usable but slow (worst case ~85s) at 8. The test users were provisioned
and torn down completely afterward (LDAP + Postgres), same cleanup
discipline as every other phase's live testing.

Phase 7 (ADR 0016) added `apps/mobile` — a React Native / Expo app
covering document browsing/search, AI chat, tasks, and the entity graph,
read-mostly by design (no upload, no Legal Draft, no App/Play Store
distribution yet — see the ADR for why). Reuses the same
`lib/api.ts`/`lib/auth.tsx` shape as `apps/web`, talks directly to
`https://v78281.1blu.de` (Phase 6a's public HTTPS made this
straightforward — no tunnel or CORS concerns for a native app), and
ports the entity graph's radial SVG layout to `react-native-svg` with
the Phase 5c click-target fix built in from the start rather than
re-discovered. Verified with a real device over Expo's tunnel mode, not
just `tsc`/`vitest` — which is what caught two real bugs neither of
those would have: the project was initially scaffolded against Expo SDK
57, one release ahead of what the currently-published Expo Go app
actually supports (confirmed via Expo's own version API, not assumed),
requiring a downgrade to SDK 54; and React Native's `fetch` doesn't
reliably serialize a `URLSearchParams` body the way browser `fetch`
does, which silently sent an empty login request and got rejected by
the backend — fixed by building the encoded string directly, with a
regression test added.

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

## Production deployment

```bash
# Build the static frontend bundle (lands in apps/web/dist, same-origin
# API base URL so it works behind the reverse proxy):
docker compose exec -e VITE_API_URL='' web sh -c "cd /app/apps/web && pnpm build"

# Start (or reload after a rebuild) the TLS-terminating reverse proxy:
docker compose --profile prod up -d caddy
```

Re-run both after any frontend change you want live at
https://v78281.1blu.de — the `dist/` build is static, it does not
auto-rebuild like the dev server does. `api` and the dev server's ports
are host-local only (`127.0.0.1`); Caddy is the only thing meant to be
reachable from the public internet on this host, on 80 (redirects to
443) and 443.

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
5. Frontend integration (done) — split into:
   - 5a (done): auth (login, JWT, protected routes), document library
     (list, upload, detail, search)
   - 5b (done): AI chat UI, Legal draft UI, Task list UI
   - 5c (done): entity graph explorer (searchable list + one-hop SVG
     radial view, click-to-recenter for multi-hop exploration)
6. Production readiness — split into:
   - 6a (done): TLS + reverse proxy (Caddy, automatic HTTPS), production
     frontend build, close direct public access to `api`/dev server
   - 6b (done): automated Postgres/LDAP/Signal-key backups + verified
     restore procedure (`docs/runbooks/backup-restore.md`)
   - 6c (done): health watchdog (containers, internal+public
     `/health`, disk usage) alerting over Signal on state transitions
   - 6d (done): load testing (`docs/runbooks/capacity.md`) — comfortable
     up to ~2 concurrent chat/draft users on this CPU-only host, usable
     but slow up to ~8; Ollama's `NUM_PARALLEL:1` is the bottleneck, not
     the database
7. Mobile app (done) — React Native/Expo, `apps/mobile`. Document
   browsing/search, AI chat, tasks, entity graph. Read-mostly (no
   upload, no Legal Draft); testable build only, no store distribution
   yet. See ADR 0016.
