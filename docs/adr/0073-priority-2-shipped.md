# 0073 — Priority 2 (CI/CD, E2E, logging, Sentry, quality): what shipped

## Status

Accepted

## Context

ADR 0066 (the enterprise-SaaS audit) queued Priority 2 pending explicit
go-ahead; ADR 0067 recorded Priority 1 as complete. This ADR records what
actually shipped from the Priority 2 list (`docs/adr/0066` §Priority 2)
and closes it out the same way ADR 0067 did for Priority 1, including an
updated SaaS-readiness table.

All five items shipped on `feat-priority-2-logging-sentry-quality`
(22 commits), merged via PR #110 with all 8 CI checks green (backend,
frontend, security, e2e/Playwright, and 4 Docker build validations).

## Decision — what shipped

1. **CI/CD pipeline** (ADR 0068) — 5-job GitHub Actions workflow
   (frontend, backend, security report, Playwright e2e, Docker build
   validation ×4), fail-fast, dependency caching, no secrets in the repo.
2. **Playwright smoke suite** (ADR 0069) — landing, login/auth flow,
   dashboard, AI chat availability, document listing, admin access,
   settings/profile, responsive layout, across desktop + mobile viewports.
3. **Structured logging** (ADR 0070) — JSON formatter, per-request
   correlation IDs via a `ContextVar`, a catch-all exception handler for
   clean 500s with full server-side detail.
4. **Sentry error tracking** (ADR 0072) — backend + frontend, built after
   the logging foundation per the required ordering. Privacy-hardened
   beyond the SDKs' own defaults: `send_default_pii=False`,
   `include_local_variables=False`, an `EventScrubber` denylist extended
   with this app's sensitive field names, a `before_send` text-redaction
   hook for Dutch postal codes/IBANs/phone numbers/BSNs, and the
   frontend's `dataCollection` object (not the deprecated
   `sendDefaultPii`) disabling cookies/headers/query params/stack
   variables. Session Replay and Profiling deliberately not enabled.
5. **Quality improvements** (ADR 0071) — FK indexes
   (`documents.residency_id`, `tasks.created_by`), focus-trap + full ARIA
   on `Modal`/`Drawer`/`CommandPalette`/`Tooltip`/`ShortcutsSheet`,
   responsive fixes on `Workspace.tsx`.

## A pre-existing bug found and fixed along the way

Six backend test files (`test_document_reprocess.py`, `test_tasks.py`,
`test_document_classification_events.py`, `test_documents.py`,
`test_planning_engine.py`, plus one gap in `test_notify_due_tasks.py`)
let a document reach "ready" status without disabling all six
`auto_extract_*_on_ready`/`auto_classify_on_ready` settings flags. Left
enabled and unmocked, each fires a real `chat_completion` call toward an
unreachable Ollama via the `EMBEDDINGS_CREATED` event — DNS resolution
fails fast, but `events.py`'s per-handler retry backoff (1s/5s/15s ×
up to 6 handlers) turned every affected upload into anywhere from ~20
seconds to several minutes of dead time, compounding into the 20+ minute
CI runs that motivated building this pipeline in the first place. Fixed
by disabling every flag/mocking every extraction call these tests don't
need, matching the pattern already established elsewhere in the suite.
Verified: the full 762-test backend suite now runs in under 25 seconds
locally with zero hangs.

Three more real, CI-reproducible bugs surfaced only once the pipeline
ran to completion for the first time (masked until now by the hang
above and the OpenLDAP race fixed earlier in this branch):

- **CORS misconfiguration in the e2e job**: `CORS_ALLOWED_ORIGINS`
  defaulted to the vite dev-server port (5173), but the e2e job serves
  the built frontend on 4173 (`vite preview`). Every browser call the
  Playwright suite made to the API was silently CORS-blocked, so
  `fetchMe()` failed on every authenticated page and `ProtectedRoute`
  bounced straight back to `/login` — the actual cause of all 8
  Playwright failures, not flakiness. Fixed in `ci.yml`.
- **Phone-number collision**: `test_notify_due_tasks.py` and
  `test_chat.py` both hardcoded `+15559990001`/`+15559990002`; whichever
  test file ran first claimed the number, leaving the other's phone-link
  call a 409 and silently zeroing out its notification count.
- **Stale RDW mock + entity-status filter**: a vehicle-detection test
  mocked "RDW confirms this plate doesn't exist" (which the app
  correctly refuses to persist) instead of "RDW lookup failed"
  (transient, still persists unenriched), and queried `GET /entities`
  without `status=all` — vehicles, like every extracted entity, start
  `pending_review` under the entity-review-queue design, so the default
  confirmed-only listing never had a chance of finding it regardless of
  the mock.

None of these were introduced by this branch's own feature work; they
were latent defects in the existing test suite/CI config that this
branch's fixes to the *hang* bug (above) finally allowed CI to run far
enough to expose.

## Verification

- Full local backend suite: 762 tests, 0 hangs, ~25s (was: routinely
  20+ minutes, sometimes cancelled).
- CI run (all 8 jobs green): frontend, backend, security (report-only),
  Playwright e2e (desktop + mobile), 4× Docker build validation.
- No production deployment was performed — Priority 2's instructions
  explicitly excluded auto-deploy; the DSNs behind Sentry are known only
  to this session and the user, and are inert until set in a real
  environment's `.env`.

## Updated SaaS Readiness (0–100)

Baseline from ADR 0066, before Priority 1:

| Category | Before P1 | After P1 (ADR 0067) | After P2 (this ADR) | Why it moved |
|---|---|---|---|---|
| MVP | 90 | 90 | 90 | Already exceeded; unchanged by P2 |
| Beta | 80 | 80 | **92** | The two gaps ADR 0066 called out here — "no CI gate / no APM" — are both closed |
| Public Launch | 45 | 50 | **68** | Of ADR 0066's 5 gaps (billing, security headers, CI/CD, APM, E2E), only billing remains; CI/CD, APM, E2E all shipped this pass |
| Enterprise | 25 | 25 | 25 | RBAC 2.0/Teams, SSO federation — untouched, not in scope |
| App Store (iOS) | 55 | 55 | 55 | Unaffected by backend/CI work |
| Google Play | 55 | 55 | 55 | Unaffected by backend/CI work |
| Self-hosted edition | 70 | 70 | **74** | Structured logging + FK indexes + a real CI gate make a redistributable install meaningfully more operable/debuggable, though packaging itself is untouched |

## Consequences

- Remaining local-only test failures (documented, not fixed): fixed
  usernames/phone numbers/task titles reused across this long working
  session's many local test runs against one persistent Postgres
  produce `IntegrityError`/`MultipleResultsFound`/inflated-count
  failures that do not reproduce against CI's fresh-per-run Postgres
  (confirmed directly: CI showed 4 real failures where local showed 29).
  Not fixed here as out of scope for Priority 2; a future pass could add
  `_unique()`-style helpers to the remaining fixed-value test fixtures.
- `test_upload_triggers_vehicle_detection_and_creates_entity`,
  `test_notify_due_tasks.py`, and the e2e CORS config were latent,
  pre-existing defects unrelated to this branch's own feature work,
  fixed as a side effect of finally getting CI to run to completion.
- Billing/payments remain the single largest gap standing between
  "Public Launch" and a materially higher score — not part of Priority
  2's scope and not started here.
- Priority 3 (ADR 0066): route-level code splitting, Paperless thumbnail
  proxying, AI Gateway call caching, splitting `models.py`/`api.ts` by
  domain, pre-commit ruff/tsc enforcement, README refresh — all still
  queued, none started.
