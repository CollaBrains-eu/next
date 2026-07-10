# 0061 — Manager Agent multi-round + document categories: production deploy

## Status

Done and verified live on `v78281.1blu.de` as of 2026-07-10.

## Context

ADRs 0059 (Manager Agent multi-round) and 0060 (document categories) landed
their respective feature branches, each fully reviewed task-by-task via
subagent-driven-development plus a final whole-branch review. Per this
project's standing "direct to server, no PR flow" practice, both branches
were merged straight into `main` and deployed live. This ADR documents that
deploy: three real, previously-undetectable bugs it surfaced, and a
production data cleanup performed alongside it.

No sandbox available anywhere in this session had Docker/Postgres, so all
nine implementation tasks and the final whole-branch review were verified by
hand-tracing code against mocks — thorough, but incapable of catching
anything that only manifests against a real running stack. All three bugs
below are exactly that category: invisible to code review, real at deploy
time.

## Bugs found and fixed during this deploy

**1. Migration imported application code, crashing `alembic heads`/`upgrade
head`.** `0026aa5966bf_create_categories_table.py` did
`from api.document_categories import DOCUMENT_CATEGORIES` at module level.
Alembic resolves the full revision graph — loading every version file's
module — before `env.py`'s `sys.path.insert(0, .../src)` runs, so any
`api.*` import at a migration's top level raises `ModuleNotFoundError` for
every command that walks the graph. `alembic current` masked this (it
doesn't need the full graph); `alembic heads` and `upgrade head` both
crashed. Fixed by inlining the 25-row taxonomy directly into the migration
file — the correct fix regardless, since migrations should be immutable
snapshots and not depend on application code that changes after the
revision is written.

**2. Caddy never learned the new `/categories` route.** The reverse proxy
disambiguates the SPA from the API by a hardcoded `path` allowlist in the
`@api` matcher (see ADR 0012/Phase 6a). `/categories` was never added to it,
so every request silently fell through to `index.html` regardless of
`Accept` header — no error, just the wrong response, which is why this
wasn't caught by a straightforward `curl` smoke test until the response
body was actually inspected. Fixed by adding `/categories*` to the
matcher and restarting Caddy (a `caddy reload` was attempted first but the
running process did not appear to pick up the bind-mounted file's new
content; a full container restart did).

**3. Pre-existing, unrelated test failures confirmed out of scope.**
`test_documents.py::test_upload_triggers_vehicle_detection_and_creates_entity`
and `test_entities.py::test_extract_entities_deduplicates_by_case_insensitive_name_and_type`
failed both in the full suite and in isolation. Verified via a direct A/B
run against a throwaway image built from the pre-merge commit (`578e8d6`):
both failed identically against the old code. Confirmed pre-existing and
unrelated to this deploy; not fixed here.

## Deploy sequence actually used

Manual `pg_dump` backup (in addition to the existing daily cron backup) →
`docker compose build api` → `alembic upgrade head` against live Postgres →
full backend suite (`python -m pytest tests`, `PYTHONPATH=/app/src` — the
image has no properly wired editable install, same class of issue as bug
#1) → `docker compose up -d api` → frontend vitest gate in the bind-mounted
`collabrains-web-1` container → `vite build` → live verification (category
filter, Manager Agent multi-round tool call, `/chat` — Signal's actual
bridge target — all exercised through a real authenticated browser session,
plus confirming `signal-bot`/`signal-cli` stayed healthy with zero new
errors in their logs throughout).

## Production data cleanup

Separately requested: the shared dev/prod Postgres had accumulated 5,043
pytest-fixture users (and their cascading documents/vehicles/entities/
tasks/cases/ai_call_log rows) across many historical unpruned test runs —
the same recurring test-isolation issue noted in this project's history,
grown substantially worse since the last cleanup. Reduced to the 3 real
accounts (`alice`, `admin1`, `signal-bot`) and their 10 real documents via
one atomic, FK-ordered transaction, preceded by a fresh backup and a
dry-run count check. 6 correspondingly orphaned Paperless-ngx documents
(the actual OCR'd file blobs, tracked separately from Postgres via
`documents.paperless_id`) were identified by diffing Paperless's full
document list against the 8 non-null `paperless_id` values among the kept
10, and deleted via Paperless's own REST API. The test suite run performed
as part of this same deploy recreated a smaller batch of fixture rows as an
expected side effect; the same cleanup was re-run once verification was
complete, restoring the same clean baseline.

## Consequences

- Migrations in this repo must not import from `api.*` (or anything outside
  the `alembic/` tree) at module level. Worth a lint rule if this recurs.
- Caddy's `@api` path allowlist is a manual, easy-to-forget step for any new
  top-level route — not caught by any existing automated check. No fix
  proposed here beyond documenting it; a route-list-generation script would
  remove the manual step but is out of scope for this deploy.
- The shared Postgres test-isolation problem (documented multiple times in
  this project's history) is still unresolved at the root — this cleanup is
  a repeat of the same manual fix, not a permanent one. A per-test-run
  schema/transaction-rollback isolation strategy would prevent recurrence
  but is a larger change than this deploy's scope.
