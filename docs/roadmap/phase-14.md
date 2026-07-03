# Phase 14 — Enterprise

## Goal

Turn CollaBrains from a single-tenant application into a platform:
organizations, teams, shared AI memory within a team, policies, AI
governance, tenant isolation, and a real RBAC model (`RBAC 2.0` — the
existing `User.role` field from ADR 0001 is a single flat role per
user, not a permission system).

## Why now

Every phase so far assumes one flat set of users sharing one Postgres
database (ADR 0001's `User.role` is `member`/`admin`/`service` —
no organization boundary at all). Phase 13's per-user personal AI and
Phase 9's per-tool permissions both become substantially harder to get
right retroactively once there's real multi-tenant data — better to
design tenant isolation before Phase 13/9 data accumulates without it,
if Phase 14 is sequenced after them; this ordering tradeoff should be
revisited when Phase 9/13 are actually scheduled.

## New concepts

- **Organizations** — the tenant boundary. Every user, document,
  memory, and case (Phase 10) belongs to exactly one organization.
- **Teams** — a grouping within an organization, likely the actual
  sharing boundary for "shared AI memory" below (not every org member
  should see every other member's memories by default).
- **Shared AI Memory** — Phase 8b's `Memory` table is currently scoped
  to a single `user_id`. This phase needs an explicit decision on what
  team-shared memory means: a separate table, or `Memory` gaining an
  optional `team_id` alongside `user_id`.
- **Policies** — org-level rules (e.g. "drafts always require a second
  approver," extending Phase 8c's per-goal `requires_approval`
  to be org-configurable instead of hardcoded in
  `APPROVAL_REQUIRED_GOALS`).
- **AI Governance** — audit and control over what the AI is allowed to
  do org-wide — likely builds on Phase 9's permission model plus the
  existing `ai_call_log`/`reflection_log` audit tables, extended with
  an org-level view/export.
- **Tenant Isolation** — every query (documents, chat, memory, plans,
  entities) scoped by organization at the database layer, not just
  filtered in application code, to make cross-tenant data leaks a
  schema-level impossibility rather than an application bug risk.
- **RBAC 2.0** — real permission sets (Phase 9's `permissions` list on
  tool descriptors becomes assignable per role, not just per user),
  replacing the current three-value `User.role`.

## Design questions to resolve before implementation

- **Migration path**: every existing table (`documents`, `memories`,
  `plans`, `entities`, ...) needs an `organization_id` retrofitted.
  This is the highest-blast-radius migration in the project's history
  so far — needs a real plan for doing it against live data, not just
  a schema change, likely its own dedicated sub-phase before any new
  Enterprise feature work starts.
- **Single-tenant default**: does the current deployment become "one
  organization" transparently (so this phase doesn't force a disruptive
  re-registration of every existing user), or is this treated as a
  clean-slate feature only relevant to new deployments?

## Acceptance criteria

- A tenant-isolation regression test exists proving org A's user cannot
  see org B's documents/memories/plans/entities through any endpoint —
  given the "schema-level impossibility, not application bug risk"
  goal above, this should be tested adversarially, not just happy-path.
- At least one policy (e.g. approval requirement) is configurable per
  organization rather than hardcoded.
