# CollaBrains

Privacy-first AI knowledge platform. AI is the central orchestration layer;
users interact via Web, Mobile, Signal (chat-first), and later Admin.

## Status: Phase 19 — Vehicles Page (List, Plate-Styled Lookup, Case Linking)

See `docs/adr/` for the architecture decisions behind this build
(0001: scaffold, 0002: document pipeline, 0003: AI Gateway/Orchestrator,
0004: Legal/Planner agents + workflow, 0005: Signal bot, 0006: Signal
identity linking, 0007: Signal attachments & notifications, 0008: entity
graph, 0009: frontend auth & documents, 0010: chat/legal/tasks UI, 0011:
entity graph UI, 0012: TLS & reverse proxy, 0013: backups, 0014:
monitoring & alerting, 0015: load testing, 0016: mobile app foundation,
0017: event bus, 0018: long-term memory, 0019: planning engine, 0020:
reflection engine, 0021: tool registry, 0022: MCP platform, 0023:
permissions, 0024: tool discovery, 0025: knowledge graph 2, 0026:
multi-agent system, 0027: autonomous workflows, 0028: personal AI,
0029: enterprise foundation, 0030: learning platform, 0031: case/matter
workspace, 0032: sidebar shell redesign, 0033: case workspace UI,
0034: assistant UI, 0035: settings UI, 0036: vehicle entity, 0037:
vehicles page).
**All 15 phases of the original roadmap are done**, plus four further
phases built from fresh specs after the roadmap closed: Phases 0-4, all
of Phase 5 (5a, 5b, 5c), all of Phase 6 (6a, 6b, 6c, 6d), Phase 7, all
of Phase 8 (8a, 8b, 8c, 8d), all of Phase 9 (9a, 9b, 9c, 9d), Phase 10,
Phase 11, Phase 12, Phase 13, Phase 14, and Phase 15 -- every phase in
the original 7-phase plan, the mobile phase, the Cognitive Engine
roadmap, and the AI Platform roadmap that followed it. **Phase 16**
(Case/Matter Workspace), **Phase 17** (Frontend Catch-Up, split into
17a-17d), **Phase 18** (Vehicle Entity), and **Phase 19** (Vehicles
Page) followed, each starting from its own brainstormed spec rather
than a pre-written roadmap entry -- see
[`docs/roadmap/`](docs/roadmap/) for what came before and ADR
0031/0032 for why this project keeps going past a "complete" roadmap.

Two earlier phases were deliberately scoped down from their original
proposal rather than fully built, and stay that way on purpose:
**Phase 14** (Enterprise) is a foundation only -- organizations and one
policy override exist, but there's no per-table tenant isolation yet
(ADR 0029). **Phase 15** (Learning Platform) exports a real dataset
from existing feedback signal, but stops before fine-tuning,
benchmarking, or deploying a model -- this environment has no training
infrastructure to do that safely (ADR 0030). Both remain candidate
starting points for future work, alongside what Phase 16/17/18/19
themselves left open (see their ADRs, 0031-0037).

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
- **Phase 8a** — an in-process event bus (`api/events.py`): handlers are
  awaited inline so existing test-timing assumptions hold, while every
  event is also durably logged to a Redis Stream (retry with backoff,
  dead-letter queue after 3 attempts, idempotent re-dispatch) for
  audit/replay. The document pipeline (`api/documents.py`) now runs as a
  chain of events (`DocumentUploaded` → `OCRCompleted` →
  `EmbeddingsCreated` → `TasksCreated`/`EntitiesExtracted` →
  `NotificationRequested` → `WorkflowCompleted`) instead of one
  sequential function. See ADR 0017.
- **Phase 8b** — persistent AI memory (`api/memory.py`, `memories` table):
  episodic/semantic/procedural memories, embedded and retrieved by cosine
  similarity (HNSW, same strategy as document chunks), scoped per user.
  `/chat` retrieves relevant past-conversation memories and injects them
  alongside document context; after responding, a background task
  extracts a new memory from the exchange if it's worth keeping. See ADR
  0018.
- **Phase 8c** — a Planning Engine (`api/planning_engine.py`,
  `POST /plans`, `POST /plans/{id}/approve`): decomposes a goal into a
  fixed, deterministic sequence of steps (not an LLM-improvised graph —
  the same "smallest safe slice" reasoning ADR 0004 applied one level up)
  dispatched across the existing Document/Legal/Entity/Planner agents plus
  two new no-LLM aggregations (document-collection organization,
  timeline generation). A failing step is retried once, then isolated —
  it doesn't abort the rest of the plan. Goals whose output leaves the
  system (drafting) require explicit approval before they run. See ADR
  0019.
- **Phase 8d** — a Reflection Engine (`api/reflection.py`): after `/chat`
  and `/legal/draft` generate an answer, a second LLM call judges whether
  the retrieved context actually supported it, retrying retrieval once
  with a wider net if not. Wired into the same `_generate_draft` function
  the Planning Engine's Legal Agent step calls, so plan-initiated drafts
  get the same hallucination check as direct API calls. Results are
  logged to a `reflection_log` audit table; a reflection failure never
  blocks or alters the response actually returned. See ADR 0020.
- **Phase 9a** — a Tool Registry (`api/tool_registry.py`, `api/tools.py`,
  `GET /tools`): five existing capabilities (search, document
  summarization, legal drafting, task/entity extraction) registered as
  self-describing tools (name, description, permissions,
  input/output schema) rather than hardcoded into each agent — no
  capability logic rewritten, thin wrappers only. See ADR 0021.
- **Phase 9b** — an MCP Platform (`api/mcp_server.py`,
  `POST /mcp`): the tool registry exposed over the Model Context
  Protocol (Streamable HTTP transport, non-streaming). Authenticated the
  same way as every other endpoint; `user_id` always comes from the
  session, never from the request body. See ADR 0022.
- **Phase 9c** — Permissions (`api/permissions.py`): a static
  role → permission mapping (reusing `User.role`, no new tables)
  enforced inside `dispatch()` itself, the one chokepoint every tool
  call already goes through. See ADR 0023.
- **Phase 9d** — Tool Discovery: `api/tool_registry.py`'s
  `to_ollama_tools()` exports every registered tool as an
  Ollama-native function-calling definition, and
  `api/ai_gateway.py`'s `chat_completion_with_tools()` offers them to
  the model and returns any requested tool call — without executing
  it; that loop is Phase 11/12 territory. See ADR 0024.
- **Phase 10** — Knowledge Graph 2 (`api/knowledge_graph.py`,
  `GET /decisions/{id}`): a `Decision` node (the first knowledge-graph
  type beyond `Entity`, ADR 0008) created as a side effect of approving
  a Plan whose output leaves the system — approving is deciding — and a
  generalized, polymorphic `GraphEdge` table connecting it to the
  documents it was derived from, answering "which documents support
  this decision?" See ADR 0025.
- **Phase 11** — Multi-Agent System (`api/manager_agent.py`,
  `POST /manager/ask`): the model itself is the Manager — it's offered
  the calling user's permitted tools (9a, filtered by 9c's
  permissions) via 9d's native function-calling, and if it requests
  one, the tool is dispatched and the result fed back for a final
  answer. One round only; Planning Engine (8c) is untouched, this is a
  new, separate single-turn capability alongside it. See ADR 0026.
- **Phase 12** — Autonomous Workflows: the "learn" step
  (`api/memory.reinforce_memories`) closing the one part of the
  observe/plan/execute/verify/learn cycle that didn't already exist
  (Phase 8a already runs the document pipeline unattended; 8c plans;
  agents execute; 8d verifies). A memory that contributed to a
  Reflection-verified-sufficient `/chat` answer gets its importance
  reinforced -- reward only, no decay. See ADR 0027.
- **Phase 13** — Personal AI (`api/preferences.py`,
  `GET`/`PUT`/`DELETE /preferences/me`): a `UserPreference` table for
  durable, explicitly-set facts about a specific user -- distinct from
  Memory (Phase 8b), which stores facts extracted from conversations.
  Scoped to one preference, `preferred_language`, wired into `/chat`'s
  system prompt so it changes behavior across future conversations
  without being restated. See ADR 0028.
- **Phase 14** — Enterprise foundation (`api/organizations.py`,
  `GET`/`PUT /organizations/me/policies`): an `Organization` every user
  belongs to (all pre-existing users backfilled into one "Default
  Organization" via a safe nullable-then-NOT-NULL migration, verified
  against the live users table), and one real per-organization policy
  override (`approval_required_goals`, overriding Planning Engine's
  hardcoded default). Deliberately a foundation slice, not full
  multi-tenancy -- no per-table data isolation yet. See ADR 0029.
- **Phase 15** — Learning Platform (`api/learning_dataset.py`,
  `GET /learning/dataset`, admin-only): exports two real feedback
  signals already sitting in the database -- approved/unapproved Legal
  Agent drafts (a genuine instruction->draft pair with human sign-off
  as the label) and Reflection Engine quality verdicts. Deliberately
  stops at Dataset -- no Synthetic Data, Fine Tune, Benchmark, or
  Deploy stage, since this environment has no training infrastructure
  and the production host is already CPU-bound at low concurrency
  (ADR 0015). See ADR 0030.
- **Phase 16** — Case/Matter Workspace (`api/cases.py`, `api/cases_router.py`,
  `GET`/`POST /cases`, `GET`/`PATCH /cases/{id}`): a user-scoped `Case`
  table giving the "case" concept Planning Engine's `summarize_case`
  goal and `Decision`'s own docstring had assumed since Phase 8c/10 but
  never had a real identity for. `Document.case_id` is a direct FK
  (`ON DELETE SET NULL`); `Task`/`Decision` link via the existing
  polymorphic `graph_edges` table (Phase 10, ADR 0025) instead of two
  more nullable columns. Membership is optional everywhere -- no
  backfill, no existing-row risk. `POST /plans` now accepts a `case_id`
  for `summarize_case`, resolved to that case's documents before
  `build_steps()` runs. See ADR 0031.
- **Phase 18** — Vehicle Entity (`api/vehicle_agent.py`, `api/rdw_client.py`):
  a new `entity_type="vehicle"` reusing the existing `Entity`/
  `EntityMention` graph (Phase 4, ADR 0008) rather than a new top-level
  node type, so a vehicle shows up for free in `/entities` and its
  one-hop graph view, and two documents mentioning the same kenteken
  automatically share one entity. Detection is pure regex (not LLM --
  kentekens/VINs have small, fixed syntactic formats), run alongside
  the Entity Agent in the same document-pipeline event chain (Phase
  8a). RDW's open data API enriches any newly-known kenteken
  (anonymous access, no App Token yet); the same `lookup_vehicle`
  function backs both that passive pipeline hook and an active Tool
  Registry entry, automatically callable from the Manager Agent
  (`/manager/ask`, Phase 11) and MCP (Phase 9b). See ADR 0036.
- **Phase 19** — Vehicles Page (`api/vehicles_router.py`): the first
  REST surface for Phase 18's vehicle data -- `GET /vehicles` (full RDW
  payload per row) and `POST /vehicles/lookup` (a direct wrapper around
  `vehicle_agent.lookup_vehicle`, alongside its existing Tool Registry
  entry), both requiring only authentication like `GET /entities`.
  Vehicles can now link to a `Case` (Phase 16) via `graph_edges`,
  exactly like Task/Decision already do -- `POST /cases/{case_id}/vehicles/{vehicle_id}`,
  with no ownership check on the vehicle itself since entities have no
  owner. See ADR 0037.

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

Phase 17 (`docs/superpowers/specs/2026-07-04-frontend-catchup-design.md`)
closed the gap between backend capabilities shipped API-only since
Phase 8c and what `apps/web` actually exposed, split into four stacked
sub-phases. Phase 17a (ADR 0032) replaced the top nav with a persistent
left sidebar (Linear/Notion/Vercel-style), shrinking `App.tsx` to a
pure route table with the shell itself moved into new `Layout`/`Sidebar`
components, plus two new shared primitives (`Card`, `EmptyState`) with
no consumer yet in that sub-phase. Phase 17b (ADR 0033) built `/cases`
and `/cases/:id` on top of the Phase 16 backend: a dashboard with
inline "+ Attach" flows (reusing `UploadDialog.tsx`'s toggle pattern)
for linking existing documents/tasks/decisions to a case, backed by a
new `GET /decisions` list endpoint added specifically to populate the
decisions picker. Phase 17c (ADR 0034) built `/assistant`, a UI for the
Phase 11 Manager Agent (`POST /manager/ask`) — deliberately a separate
page from `/chat` rather than a mode toggle, since the two endpoints
have genuinely different contracts (stateless single-round tool-calling
vs. full-history RAG), with a `via: <tool_name>` badge making the
Manager's tool selection observable. Phase 17d (ADR 0035) built
`/settings`, a single curated-language preference UI for the Phase 13
Personal AI backend (`GET`/`PUT /preferences/me`) — intentionally the
only setting on the page, a home for future settings rather than a
sign more exist today. With all four sub-phases merged, the sidebar carries
all 8 nav items (Documents, AI Chat, Legal Draft, Tasks, Entities,
Cases, Assistant, Settings) and every one of Phase 17's three target
backend capabilities has real UI. None of 17a-17d added component-level
test coverage (this codebase has no React component testing library);
each was verified via `tsc -b` plus a real browser check against the
live stack.

Phase 19 (`docs/superpowers/specs/2026-07-04-vehicles-page-design.md`)
added a ninth nav item, `/vehicles`, giving Phase 18's backend-only
vehicle data its first UI: a new `LicensePlateInput.tsx` component
styled as a real Dutch plate (yellow, black bold text, blue "NL" band
with EU stars, confirmed via a visual mockup comparison during
brainstorming) feeds `POST /vehicles/lookup`, above a card list of
every detected vehicle (`GET /vehicles`) that distinguishes three
states via `fetched_at`/`merk` — not yet looked up, looked up but no
RDW match, or full RDW details. `CaseDetail.tsx` also gained a fourth
attach-flow section (Vehicles), identical in shape to the existing
Documents/Tasks/Decisions sections. Built as one phase rather than
split into backend/frontend sub-phases like Phase 16→17b — an explicit
choice even though it crossed both. See ADR 0037.

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
8. Cognitive Engine (done) — split into four independently deployable
   milestones, each built from `main` rather than stacked on the others:
   - 8a (done): in-process event bus with durable Redis Stream logging,
     retry/backoff, and a dead-letter queue; the document pipeline runs
     as an event chain instead of one sequential function. See ADR 0017.
   - 8b (done): persistent episodic/semantic/procedural AI memory,
     retrieved by embedding similarity and injected into `/chat`;
     extracted automatically from exchanges worth remembering. See ADR
     0018.
   - 8c (done): a Planning Engine that decomposes a goal into a fixed,
     deterministic step sequence across the existing agents, with
     retry-once-then-isolate failure handling and approval-gating for
     goals whose output leaves the system. See ADR 0019.
   - 8d (done): a Reflection Engine that reviews every `/chat` and
     `/legal/draft` answer against its retrieved context, retrying
     retrieval once if the evidence looks insufficient, and logging the
     verdict to an audit table. See ADR 0020.
9. AI Platform (done) — split into four independently-scoped
   sub-phases (9a and 9b/9c/9d were built as a stack, each on the
   previous, not independently from `main` like Phase 8 — see ADR 0022
   for why):
   - 9a (done): a Tool Registry -- self-describing, discoverable
     capabilities instead of hardcoded agent imports. See ADR 0021.
   - 9b (done): an MCP Platform exposing the registry over the Model
     Context Protocol. See ADR 0022.
   - 9c (done): Permissions -- tool access enforced against `User.role`
     inside `dispatch()` itself. See ADR 0023.
   - 9d (done): Tool Discovery -- registered tools exported as
     Ollama-native function-calling definitions. See ADR 0024.
10. Knowledge Graph 2 (done) — a `Decision` node type (the first beyond
    `Entity`) and a generalized, polymorphic `GraphEdge` table, scoped
    to the roadmap's own acceptance bar (one new node type, one new
    relationship, one real answerable question) rather than all ten
    node types the roadmap originally proposed. See ADR 0025.
11. Multi-Agent System (done) — the model itself is the Manager: offered
    the calling user's permitted tools, and if it requests one,
    `dispatch()` is called and the result fed back for a final answer.
    One round only; no new Agent-descriptor abstraction, no cost/
    priority fields nothing differentiates on yet. See ADR 0026.
12. Autonomous Workflows (done) — the "learn" step: memories that
    contributed to a verified-sufficient `/chat` answer get reinforced.
    Observe/plan/execute/verify already existed elsewhere in this
    codebase (event bus, Planning Engine, agents, Reflection Engine);
    this closes the one missing piece. See ADR 0027.
13. Personal AI (done) — one preference, `preferred_language`, in a new
    `UserPreference` table (separate from Memory -- explicit, upserted,
    never expires), wired into `/chat`'s system prompt. Scoped to the
    roadmap's own testable example rather than the three services
    (profile/preferences/context) it proposed. See ADR 0028.
14. Enterprise (foundation done) — `Organization` + `User.organization_id`
    (safe nullable-then-NOT-NULL migration, backfilled against 845 live
    users with zero test breakage), and one real per-organization
    policy override. Deliberately not the full roadmap: no per-table
    tenant isolation, no Teams, no RBAC 2.0 yet -- see ADR 0029 for
    exactly what's still missing and why the full retrofit is its own
    future phase.
15. Learning Platform (dataset export done) — `GET /learning/dataset`
    (admin-only) exports approved/unapproved Legal Agent drafts and
    Reflection Engine verdicts as real training/evaluation signal, no
    synthetic data. Deliberately stops there: no Fine Tune, Benchmark,
    or Deploy stage -- this environment has no training infrastructure
    and the production host is already CPU-bound at low concurrency
    (ADR 0015). See ADR 0030 for why faking those stages would be worse
    than not building them.
16. Case/Matter Workspace (done) — a user-scoped `Case` table,
    `Document.case_id` FK, and `Task`/`Decision` linked via the
    existing `graph_edges` table. No case-level sharing between users,
    no automatic case detection, no status workflow beyond open/closed
    -- deliberately deferred, not solved. See ADR 0031.
17. Frontend Catch-Up (done) — split into four stacked sub-phases,
    closing the gap between backend-only capabilities and `apps/web`:
    - 17a (done): sidebar shell redesign (`Layout`/`Sidebar`, `Card`/
      `EmptyState` primitives), replacing the top nav. See ADR 0032.
    - 17b (done): Case Workspace UI (`/cases`, `/cases/:id`) with
      inline attach flows for documents/tasks/decisions, plus a new
      `GET /decisions` list endpoint. See ADR 0033.
    - 17c (done): Assistant UI (`/assistant`) for the Phase 11 Manager
      Agent, with a `tool_called` badge making tool selection visible.
      See ADR 0034.
    - 17d (done): Settings UI (`/settings`) for the Phase 13 Personal
      AI language preference. See ADR 0035.
18. Vehicle Entity (done) — a new `entity_type="vehicle"` (`Entity` +
    new `Vehicle` table), regex-based kenteken/VIN detection wired into
    the document pipeline alongside the existing Entity Agent, an RDW
    open data client (anonymous, no App Token yet), and a
    `lookup_vehicle` tool usable from the Manager Agent and MCP.
    Deliberately backend-only at merge time -- Phase 19 gave it a
    frontend. Other Dutch open-data sources (KVK, PDOK, CBS, Kadaster)
    are deliberately out of scope -- candidate future phases. See ADR
    0036.
19. Vehicles Page (done) — `GET /vehicles` and `POST /vehicles/lookup`
    (the first REST surface for Phase 18's vehicle data), Vehicle↔Case
    linking via `graph_edges` (same pattern as Task/Decision), a new
    `/vehicles` page with a Dutch-plate-styled kenteken input
    (`LicensePlateInput.tsx`) and a card-per-vehicle list, and a fourth
    attach-flow section on `/cases/:id`. Built as one phase rather than
    split into backend/frontend sub-phases -- an explicit choice. See
    ADR 0037.

This is every phase built so far. Phases 16-19 each started from their
own fresh spec rather than the original roadmap, which the 15 phases
above complete in full -- see [`docs/roadmap/`](docs/roadmap/) for that
history, and ADR 0031-0037 for exactly what Phase 16/17/18/19 themselves
deliberately left open (case sharing, Planning Engine/Tool Registry/MCP/
Organizations/Learning Dataset UI, other Dutch open-data sources,
unlinking a vehicle from a case, among others), alongside what Phase 14
and Phase 15 left open before them.
