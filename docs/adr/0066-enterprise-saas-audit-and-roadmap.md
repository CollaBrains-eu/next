# 0066 — Enterprise SaaS audit: findings, OSS integration analysis, and roadmap

## Status

Proposed — Priority 1 items below are approved to execute as small, independently
reviewable commits (matches existing project practice). Priority 2-4 need an
explicit go-ahead before starting, since several touch production security
config (Caddy, Docker, OpenLDAP) or represent multi-week efforts.

## Context

Requested: a full enterprise-SaaS audit (architecture, code quality, frontend,
backend, database, security, performance, testing) plus an OSS-integration
analysis, feature-gap analysis against modern AI SaaS products, SaaS-readiness
scoring, and a prioritized roadmap — before any implementation.

This is not a blind-slate audit. The repo already carries 65 ADRs, a closed
15-phase roadmap (`docs/roadmap/README.md`), and — critically — ADR 0063
already ran a full accessibility/responsiveness/contrast audit, but only of
the static design-reference artifact (`docs/design/violet-design-language.html`),
not the real shipped app. This audit builds on that record rather than
re-deriving it, and specifically checked whether the real app in
`apps/web/src/components/ui/` inherited or fixed the artifact's known bugs.

Method: four parallel read-only deep-dives (security/auth/infra, code
quality/testing/CI, performance/DB/observability, frontend UX/a11y/mobile),
each grounded in this project's actual history (prior incidents: ADR 0047
cryptominer compromise, ADR 0052 compromise-audit-closeout, ADR 0053
credential rotation) rather than a generic OWASP checklist. All findings below
are file:line-verified, not inferred.

## Findings

### Architecture

- Monorepo: `apps/{web,admin(stub),mobile,signal-bot}` + `services/api` (the
  only backend with real code — `ai-gateway`, `ai-orchestrator`, `workflow`
  logic all live inside it; the other `services/*` and `packages/{types,sdk}`
  are README-only stubs, confirmed, matching what the root README already
  claims).
- Single production host, OpenVZ container, no swap, CPU-bound Ollama — known,
  already documented (`docs/deployment/ai-optimization.md`), not re-flagged.
- 46 Alembic migrations, additive/mature schema, no destructive changes found.
- **Root README is stale.** It's pinned at "Status: Phase 19" / ADRs through
  0037, but 28 further ADRs have shipped since (admin user-mgmt, 4 rounds of
  i18n, mobile overflow fixes, Violet DS audit, credential rotation, compromise
  closeout). Cheap, high-payoff fix: refresh the status line and phase list.
- Phase 14 (Enterprise multi-tenancy) is deliberately foundation-only —
  `Organization` + one policy override exist; no per-table tenant isolation,
  Teams, or RBAC 2.0 (ADR 0029, scoped down due to migration risk on live prod
  data). Real gap for genuine multi-org enterprise sales, not an oversight.
- Phase 15 (Learning Platform) stops at dataset export; no fine-tune/
  benchmark/deploy (no training infra) (ADR 0030).

### Security

- **[High] No OpenLDAP ACLs** — `infra/ldap/slapd.conf.template` has zero
  `access to` directives, so it falls back to `access to * by * read`: any
  bind reachable on `openldap:389` (bound to 127.0.0.1, but reachable from any
  compromised sibling container) can read every `userPassword` hash. Fix: add
  explicit ACLs (`access to attrs=userPassword by self write by anonymous auth
  by * none`).
- **[High] Backups are unencrypted, single-host** — `infra/backup/backup.sh:19-24`
  writes `pg_dump`/`slapcat` (LDAP password hashes)/Signal identity keys in
  plaintext with no offsite copy. Given the prior root compromise (ADR 0047), a
  repeat compromise takes every backup generation with it.
- **[Medium] CORS hardcoded to dev origin with credentials on** —
  `services/api/src/api/main.py:40-46`, `allow_origins=["http://localhost:5173"]`
  + `allow_credentials=True` shipped unchanged to prod. Harmless today only
  because Caddy proxies same-origin; a future "just widen it" fix would open
  real cross-origin token theft. Derive origins from env.
- **[Medium] No security headers anywhere** — `infra/caddy/Caddyfile` has no
  CSP/HSTS/`X-Frame-Options`/`X-Content-Type-Options`. Combined with JWT in
  `localStorage` (`apps/web/src/lib/api.ts:8-20`), a single XSS bug has no
  defense-in-depth backstop.
- **[Medium] API container runs as root, `--reload` in prod** —
  `services/api/Dockerfile` has no `USER`, and the prod `CMD` still passes
  uvicorn `--reload`.
- **[Medium] Weak default JWT secret fallback** —
  `services/api/src/api/config.py:9`, `jwt_secret: str = "dev-only-secret"`.
  ADR 0053 already fixed one real incident from this class of bug
  (`.env.example` placeholder shipped to prod, forged admin JWTs), but there's
  still no startup assertion refusing a known-placeholder secret — the same
  mistake could recur silently.
- **[Low] `.env` committed then untracked, not history-scrubbed** (placeholder
  values only, no live secret exposed) — worth a `git filter-repo` pass for
  hygiene, not urgent.
- **[Low] LDAP bind-DN built via unescaped string interpolation** —
  `services/api/src/api/ldap_auth.py:47` — no DN-escaping; impact limited to
  malformed-bind failures since impersonation still requires the real password.
- **Confirmed fixed and durable, not re-flagged**: tasks-ownership authz has
  explicit regression tests (`services/api/tests/test_tasks.py`); ownership
  checks (`_can_access_task`/`_can_read_document`) are consistently applied;
  `is_active` deactivation is enforced per-request in both `get_current_user`
  and the Signal on-behalf-of path; JWT algorithm is pinned server-side; no
  raw-SQL injection surface (SQLAlchemy ORM throughout); no
  `dangerouslySetInnerHTML`; Signal bot's service JWT is correctly scoped to
  zero standing permissions.
- Dependency versions weren't live-CVE-scanned — run `pip-audit` on
  `services/api` and `pnpm audit` on `apps/web` for a definitive list.
  `python-jose` is worth that scan specifically (comparatively unmaintained).

### Code Quality

- No genuine test-coverage gap: the apparent "untested router" list (feedback,
  memories, onboarding, plans, sharing, users, workspace routers) turned out to
  be a filename-convention artifact — all are exercised, just from
  scenario-named test files (e.g. `test_workspace_sharing.py` covers
  `workspace_router.py`). 760 backend test functions / ~80 files, 85 frontend
  test files — consistent with claimed growth, not inflated.
- **Broken lint script** — `apps/web/package.json:9` (`"lint": "eslint ."`) —
  `eslint` is not installed anywhere in the repo (no lockfile entry, no config
  file). `pnpm lint` fails outright today.
- No enforcement mechanism at all: no pre-commit hooks, no Husky, no CI. Ruff
  (Python) and `tsconfig.json`'s genuinely strict TS settings are both
  opt-in-only — nothing stops an unlinted/untyped commit.
- No meaningful dead code or duplication found on spot-check (`address_parser.py`
  vs `contact_parser.py` looked similar but are deliberately, documentedly split).
- Complexity hotspots worth splitting eventually: `services/api/src/api/models.py`
  (858 lines, every SQLAlchemy model in one file) and
  `apps/web/src/lib/api.ts` (1,107 lines, monolithic API client). Not urgent,
  but both will keep growing with every feature.
- No frontend/backend DTO mapping layer — `packages/types` is a stub; frontend
  types pass backend Pydantic field names through verbatim (snake_case
  included). Internally consistent, just not a real translation layer.
- `.venv-test/` and `.pytest_cache/` are excluded only via their own
  auto-generated nested `.gitignore`s, not the root one — fragile; add them to
  the root `.gitignore` explicitly.

### Testing / CI-CD

- **No E2E suite exists at all** — no `playwright.config.*`, no `playwright`
  in the lockfile, no `.spec.ts` files anywhere. Practice is genuinely manual:
  `deploy_collabrains.sh` ends by printing `curl` commands for a human to run,
  and dozens of ADRs cite manual browser verification as the actual acceptance
  method.
- **No CI/CD pipeline anywhere** — no `.github`, `.gitlab-ci.yml`, `.circleci`,
  or equivalent. Deploy is a manual SSH-run bash script
  (`deploy_collabrains.sh`) with **zero automated test/lint gate** before
  `docker compose up -d` — its own "verify" step is manual `curl` invocations
  for the operator.

### Database

- **Missing FK indexes**: `documents.category_id`, `documents.residency_id`,
  `tasks.created_by` have no `op.create_index` anywhere in
  `alembic/versions/`, unlike sibling FKs (`owner_id`, `case_id`,
  `document_id`), which are all indexed — sequential scans on category/
  residency/creator filters.
- Cascade behavior is sound where reviewed (`DocumentChunk`/`Task.document_id`
  → `CASCADE`, matching ORM-level config); `Case.user_id` has no `ondelete`
  (defaults RESTRICT), consistent with soft-delete-only users — a deliberate
  choice worth documenting as such, not an oversight.
- New N+1 found: `services/api/src/api/cases_router.py:189-190`
  (`list_my_invitations_endpoint`) issues 2 extra `db.get()` calls per pending
  invitation inside a list comprehension. Low blast radius (small lists), same
  anti-pattern as the already-fixed one in `cases.py`. `documents.py` and
  `tasks.py` list endpoints are clean (single query / correlated `EXISTS`).

### Performance / Observability

- **No query-result or AI-response caching at all.** Redis is used correctly
  for rate limiting, WebAuthn challenges, and event-stream dedup — but nothing
  caches deterministic AI Gateway calls (entity extraction, classification) by
  content hash, despite Ollama being the documented bottleneck.
- **No route-level code splitting** — `apps/web/src/App.tsx:11-29` statically
  imports all 19 route components; zero `React.lazy`/dynamic `import()`
  anywhere in the frontend. Every route ships in the initial bundle on a
  memory-capped build host.
- **No thumbnails** — `services/api/src/api/documents.py:556-585` proxies the
  full original file from Paperless-ngx for both preview and download, even
  though Paperless already generates a `/documents/{id}/thumb/` during OCR
  ingestion. Multi-MB files served for grid/list previews on a
  bandwidth/CPU-constrained host.
- **No fetch-layer caching/dedup** — no TanStack Query/SWR; every route mount
  re-fetches from scratch via plain `fetch()`.
- **AI Gateway has no circuit breaker** — a slow/overloaded Ollama just queues
  callers behind its `asyncio.Semaphore(1)` until the full timeout fires, per
  request, with no fast-fail degradation path.
- **No structured logging, no request-ID correlation, no APM.** ~19 modules
  call `logging.getLogger(__name__)` but `main.py` never configures a
  formatter; zero `sentry_sdk` references anywhere. Only observability is
  `infra/monitoring/watchdog.sh` — binary health checks with Signal alerts on
  state transitions, no metrics/latency data at all.

### Frontend / UX / Accessibility / Mobile

- **The live WCAG contrast failures from ADR 0063 were never fixed — they're
  live in production, not just in the reference doc.** `apps/web/src/styles/tokens.css`
  defines the exact same failing hex values ADR 0063 computed
  (`--text-3` 2.54:1, `--accent` 3.71:1, `--success` 3.00:1, `--danger`
  3.76:1, all below the 4.5:1 bar). This is the single highest-priority
  finding in this audit — it affects real users today.
- Real app is materially better than the artifact in several ways the ADR
  0063 audit couldn't see: icon-only buttons consistently have `aria-label`
  (often i18n-routed); `Dropdown.tsx` has `aria-expanded`/`role="menu"`;
  `Modal.tsx` has `role="dialog"`/`aria-modal`; list views (Tasks, Cases,
  Workspace-documents) have real skeleton/empty/error states, not
  blank-or-spinner.
- But coverage is uneven, not systemic: `Drawer.tsx` and `CommandPalette.tsx`
  have no `role="dialog"`/`aria-modal` at all (only Modal.tsx does); no overlay
  has a real focus trap or focus-restoration (`useEscapeToClose.ts` only binds
  Escape); only 9 of 26 `ui/` components have any `aria-*` at all —
  `Tooltip.tsx` and `ShortcutsSheet.tsx` have none.
- **`Workspace.tsx` (the case/document workspace — highest-traffic screen) has
  zero responsive breakpoint classes**, same for `Vehicles.tsx`, `Settings.tsx`,
  `ShareResolve.tsx` — likely to reproduce the artifact's "controls run
  off-screen at 375px" failure in production.
- `EntityGraph.tsx:13-17` hardcodes 5 category colors with no token mapping —
  bypassed the design-token system entirely.
- i18n is genuinely near-complete (81 `t()` calls in AdminDashboard alone,
  clean spot-checks elsewhere) but `Vehicles.tsx` hardcodes Dutch RDW-lookup
  strings directly in JSX despite importing `useTranslation` — a page the i18n
  passes (0051/0055/0056/0058) evidently missed.
- Mobile (`apps/mobile`) is further along than expected: real bundle IDs,
  adaptive icon set, and a real `eas.json` with dev/preview/production +
  submit profiles — not Expo-Go-only. Gap: no `splash` key in `app.json`
  despite an unused `splash-icon.png` asset sitting in `assets/` — default
  Expo splash ships instead of the branded one.

## OSS Integration Analysis

**Already integrated — do not re-recommend:** Paperless-ngx (OCR/doc
ingestion), OpenLDAP (auth directory), Ollama (local LLM serving), pgvector
(embeddings/semantic search — a deliberate choice over Qdrant/Weaviate/Chroma,
ADR 0002), Caddy (TLS reverse proxy), Redis (rate limiting/event streams),
signal-cli (chat channel).

**Defined but unused:** Elasticsearch is in `docker-compose.yml` behind a
profile but disabled — this host's OpenVZ container can't raise
`vm.max_map_count`, which ES 8.x requires. Decide: fix the host if hybrid
search genuinely needs it beyond Postgres-native search, or remove the dead
service definition to shrink operational surface.

**Recommended additions:**

| Tool | Why | Effort | Value | License |
|---|---|---|---|---|
| Sentry | Closes the "no APM/error tracking" gap; SDK already available in this environment | XS (hours) | High | MIT SDK / self-host or SaaS |
| Playwright | Closes "no E2E, no CI test gate"; official, zero license risk | S–M (smoke suite first) | High | Apache-2.0 |
| pre-commit + Husky/lint-staged | Enforces already-configured ruff + strict tsc instead of leaving them opt-in | XS | Medium | MIT/BSD |
| Prometheus + Grafana | Real metrics beyond binary watchdog checks | M | Medium | Deferred — budget scrape overhead against an already resource-capped host; do Sentry + structured logs first |

**Explicitly not recommended:**
- **Keycloak/Authentik** — LDAP is a deliberate, working auth path; swapping
  identity providers is a major migration not justified by any finding here.
- **n8n/Activepieces** — workflow logic is custom-built into `services/api`
  and already covers planning/reflection/tool-registry; a generic workflow
  engine would duplicate, not improve, existing functionality.
- **Meilisearch/Typesense** — Postgres-native hybrid search was already chosen
  deliberately over Elasticsearch (ADR 0002); a third search engine
  contradicts that decision.

## Feature Gap Analysis

**Already built — do not re-build:** organizations (foundation), knowledge
graph, multi-agent system, autonomous workflows, personal AI/long-term
memory, tool registry + MCP platform, permissions, reflection/planning
engines, learning-dataset export, admin dashboard (user mgmt), audit/activity
trail, document sharing, notifications service, mobile shell, Signal channel,
i18n (mostly), passkey/WebAuthn auth.

**Missing, by business impact:**
1. Billing/subscriptions — nothing found anywhere. Blocks any paid-SaaS
   motion; not urgent while usage is internal/self-hosted.
2. Full multi-tenant isolation (Teams, per-table RBAC 2.0) — blocks
   multi-org enterprise sales (Phase 14 deliberately stopped short, ADR 0029).
3. CI/CD + automated test gate before deploy — zero gate today; risk grows
   with team/change velocity.
4. APM/error tracking + structured logging — currently blind to prod errors
   beyond binary health checks.
5. E2E coverage — zero automated UI regression protection.
6. Public developer story (API keys/SDK) — `packages/sdk` is a stub.
7. Marketplace/plugin system — absent; low priority pre-multi-tenant.
8. Security headers/CSP/HSTS + encrypted offsite backups — concrete,
   low-effort hardening surfaced by this audit.

## SaaS Readiness (0–100)

| Category | Score | Why |
|---|---|---|
| MVP | 90 | Already exceeded — 500+ tests, live prod users |
| Beta | 80 | Live and used, but no CI gate / no APM is risky at wider scale |
| Public Launch | 45 | Missing billing, security headers, CI/CD, APM, E2E |
| Enterprise | 25 | No RBAC 2.0/Teams, no SSO federation (LDAP-only) |
| App Store (iOS) | 55 | EAS + bundle IDs further along than expected; splash screen unwired, no submission dry run yet |
| Google Play | 55 | Same EAS/Android maturity, same caveats |
| Self-hosted edition | 70 | Already effectively self-hosted/single-tenant by design; needs the weak-default-JWT-secret fix and packaging polish to be a clean redistributable |

## Decision

Execute **Priority 1** now, as small independently reviewable commits, each
verified before commit (matches rule 9 and the Phase 7 instructions already
given). Hold **Priority 2–4** for explicit go-ahead — several touch
production security surface (Caddy, Docker, OpenLDAP) directly.

### Priority 1 (Critical) — effort / value
- Fix live WCAG contrast failures in `tokens.css` — S / High (affects real users today)
- Add CSP/HSTS/`X-Frame-Options`/`X-Content-Type-Options` to Caddyfile + fix CORS origin config — S / High
- Add OpenLDAP ACLs (protect `userPassword`) — S / High
- Encrypt + offsite-replicate backups — S/M / High (given prior compromise history)
- Fix broken `pnpm lint` (install eslint + config, or remove the dead script) — XS / Medium
- Non-root Docker user + drop `--reload` from the prod API image — XS / Medium

### Priority 2 (High)
- Stand up Sentry — XS/S / High
- Minimal CI pipeline (run existing pytest + vitest on PR) — S/M / High
- Playwright smoke suite (login + one core flow) — S/M / High
- Fix `Workspace.tsx`/`Vehicles.tsx` responsive + i18n misses found here — S / Medium
- Add missing FK indexes (`documents.category_id`/`residency_id`, `tasks.created_by`) — XS / Medium
- ARIA/focus-trap parity for `Drawer`/`CommandPalette`/`Tooltip`/`ShortcutsSheet` — S / Medium

### Priority 3 (Medium)
- Route-level code splitting (`React.lazy`) for heavy/rare routes — S / Medium
- Proxy Paperless-ngx thumbnails instead of full-file previews — S / Medium
- Content-hash caching for deterministic AI Gateway calls — S / Medium
- Split `models.py` and `api.ts` by domain — M / Medium (not urgent)
- pre-commit/Husky enforcement of ruff + tsc — XS / Medium
- Refresh root README (stale since ADR 0037) — XS / Medium

### Priority 4 (Future)
- Multi-tenant RBAC 2.0 / Teams (Phase 14 continuation) — L / High, only once real multi-org demand exists
- Billing/subscriptions — M/L / High, only once there's a paid-customer motion
- Prometheus + Grafana — M / Medium, defer until host headroom exists
- Developer SDK / public API keys — M / Medium
- Decide fate of the unused Elasticsearch service definition — XS / Low

## Consequences

Priority 1 closes the most concretely-exploitable and most concretely-visible
gaps (live contrast failures, missing security headers, an unlocked LDAP
directory) without touching product scope. Priority 2 buys the safety net
(CI, APM, E2E) that every later phase needs to move fast without regressing
prod. Priority 3 is pure quality-of-life/performance. Priority 4 is
deliberately deferred — multi-tenancy and billing are real, multi-week
efforts that should start from their own brainstormed spec (per
`docs/roadmap/README.md`'s own stated discipline for "if there's a Phase
16"), not be bundled into this audit's roadmap.
