# ADR 0012: Phase 6 Production Readiness (split 6a/6b/6c/6d)

## Status
Accepted (6a in progress)

## Context
Phases 0-5 built a fully working product end to end, but the deployment
itself was never hardened past "works for direct development access":
the FastAPI backend (port 8000) and the Vite *dev server* (port 5173,
not a production build) are both bound to `0.0.0.0` and reachable
directly from the public internet over plain HTTP, with no TLS, no
reverse proxy, and no automated backups. "Production readiness" is too
broad for one commit — same reasoning as every prior multi-capability
phase in this project — so it's split:

- **6a (this ADR's immediate scope)**: TLS + reverse proxy + close the
  direct-exposure gap. This is the most urgent piece: right now anyone
  on the internet can hit the API directly over unencrypted HTTP.
- **6b (deferred)**: automated Postgres backups + documented restore
  procedure, plus backing up the other stateful secrets that only exist
  on this one host (Signal registration keys, LDAP data).
- **6c (deferred)**: monitoring/alerting on top of the existing
  `/health` and `/health/ready` endpoints (built in Phase 0/1b) —
  reusing the Signal bot as the alert channel rather than standing up
  new infra.
- **6d (deferred)**: load testing to document actual capacity limits
  given this host is CPU-only for Ollama inference — "production ready"
  here means knowing and documenting the real ceiling, not achieving a
  specific throughput number that was never a stated requirement.

## Decisions for 6a

**Domain**: the hosting-provider-assigned hostname `v78281.1blu.de`
already resolves to this server's public IP (confirmed directly, not
assumed) — no separate DNS decision is needed to get a real
Let's-Encrypt-issued TLS certificate.

**Reverse proxy**: Caddy, not nginx+certbot. Caddy's automatic HTTPS
(built-in ACME client, renews itself) means zero extra cron jobs or
certbot hooks — one binary, one Caddyfile, consistent with this
project's running pattern of avoiding infrastructure beyond what's
needed (Postgres-native search over Elasticsearch, in-process triggers
over Celery, hand-written types over codegen, a hand-written SVG graph
over a layout library).

**Port exposure — apply the *exact* fix already proven correct twice in
this project** (Postgres/Redis in Phase 0, Ollama/Paperless/Elasticsearch
in Phase 1b: both were caught publicly exposed on `0.0.0.0` and rebound
to `127.0.0.1`): UFW alone is not sufficient, because Docker's
`-p host:container` port publishing writes its own iptables DNAT rules
that UFW does not filter by default — a `ufw deny 8000` would NOT have
actually blocked port 8000 while Compose still published it on
`0.0.0.0:8000`. The real fix, applied here the same way: rebind `api`'s
and `web`'s Compose port mappings to `127.0.0.1:8000:8000` and
`127.0.0.1:5173:5173` (host-local only, still reachable for direct
debugging via SSH tunnel, exactly as used throughout Phase 5's browser
QA sessions). Caddy reaches both over the internal `collabrains-net`
Docker network by service name (`api:8000`), never through the published
host port, so this isn't a routing change for it. UFW then only needs
`80` and `443` open publicly; the `8000`/`5173` "dev" rules get removed
since they were never doing the job their comment claimed.

**Frontend serving**: the Vite *dev server* is not production-appropriate
(no minification/bundling, and it's a live file-watcher process, not a
static asset server). Production build (`vite build`) runs on demand
(`docker compose exec web pnpm build`, output lands in
`apps/web/dist` on the host since `apps/web` is already bind-mounted)
and Caddy serves that `dist/` directory directly as static files, with
SPA fallback (`try_files {path} /index.html`) so client-side routes like
`/documents/:id` work on a direct load/refresh. The dev workflow
(`docker compose up api web`, documented in the README) is unchanged —
this only adds a second, production-oriented way to serve the built
frontend.

**API base URL**: the frontend's API client already reads
`VITE_API_URL` at build time (`src/lib/api.ts`); the production build
sets it to an empty string so requests go to same-origin relative paths
(e.g. `/auth/token`), which Caddy routes to `api:8000` by matching the
backend's known path prefixes (`/auth`, `/documents`, `/chat`, `/legal`,
`/tasks`, `/entities`, `/search`) and serves everything else as the SPA.

## Why not more in 6a
Backups, alerting, and load testing are all independently useful without
this phase's TLS/proxy work being done first, and each has its own real
design surface (backup retention policy, alert routing, load-test
scenario selection) — bundling them in would blur what's actually a
network-security fix into a much larger, harder-to-review change.
