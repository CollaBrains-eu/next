# ADR 0009: Phase 5 Frontend Integration (split 5a/5b/5c)

## Status
Accepted (5a in progress)

## Context
Phases 0-4 built a complete backend (LDAP auth, document pipeline, hybrid
search, AI Gateway/Orchestrator, Legal/Planner agents, Signal bridge, entity
graph) but the frontend is still the Phase 0 stub: a router shell with two
placeholder pages and zero real API calls. Phase 5 is "frontend
integration" and, like every prior multi-capability phase in this project,
is too broad for one commit — it touches auth, document management, chat,
task/legal UI, and graph visualization, each with its own design surface.

## Decision: split into 5a / 5b / 5c
- **5a (this ADR's immediate scope)**: authentication + app shell +
  document library. This is the foundation every other screen depends on
  (a logged-in user and a way to see/upload documents), so it ships first.
- **5b (deferred)**: AI Chat UI (citations rendering, multi-turn history),
  Legal draft UI, Task list UI. Deferred because it's additive once 5a's
  API client/auth pattern exists — no new architectural decisions needed,
  just more routes.
- **5c (deferred)**: entity graph visualization (force-directed, consuming
  ). Deferred because it's the most visually
  complex piece and benefits from a real corpus of extracted entities to
  test against (which 5a/5b's usage will produce).

## Decisions for 5a

**Auth**: plain -based OAuth2 password grant against  (already implemented server-side, form-encoded per
 convention). Token stored in  (not
httpOnly cookie — no separate cookie-issuing endpoint exists, and adding
one is out of scope for a single-page internal tool). A 
(React context) holds the current user (from ) and exposes
login: /; an  wrapper redirects to  when no
valid session exists. No refresh-token flow — access tokens are
short-lived (see  in Settings) and re-login on expiry
is acceptable for this phase; a refresh flow is deferred until it's an
actual pain point.

**API client**: a single  fetch wrapper that attaches the
bearer token and JSON headers, with typed request/response functions per
endpoint (mirroring the backend's Pydantic models by hand — no codegen,
consistent with this project's "no infra beyond what's needed" pattern
used throughout: e.g. Postgres-native search instead of Elasticsearch,
in-process triggers instead of Celery).

**Document library**: the  route becomes a real document list (title,
status badge, created date) fetched from , an upload
dialog (, multipart), a detail view () showing OCR text/summary/chunk count, and a search bar
hitting  with results shown as title + highlighted snippet +
score. No pagination in 5a — document counts are low in this phase's usage
and infinite-scroll/pagination can be added when it's actually needed.

## Why not more in 5a
Chat, legal drafting, task management, and the entity graph are all
functionally independent screens once auth + API client exist — each adds
routes and components but no new architectural decisions. Splitting keeps
each phase reviewable and shippable on its own, consistent with every
prior phase split in this project.
