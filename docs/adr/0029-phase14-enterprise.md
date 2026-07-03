# ADR 0029: Phase 14 — Enterprise (foundation slice)

## Status
Accepted

## Context

`docs/roadmap/phase-14.md` names organizations, teams, shared memory,
policies, AI governance, tenant isolation, and RBAC 2.0. Its own design
questions flag the real risk directly: "every existing table needs an
`organization_id` retrofitted... the highest-blast-radius migration in
this project's history so far... likely its own dedicated sub-phase
before any new Enterprise feature work starts." Its acceptance criteria
are (1) a tenant-isolation regression test proving org A cannot see org
B's documents/memories/plans/entities through *any* endpoint, tested
adversarially, and (2) at least one policy configurable per
organization.

This is a live production system with real user data (deployed at
v78281.1blu.de). Unlike every prior phase's tables, which were
additive-only (a new table nobody depended on yet), retrofitting
`organization_id` onto `documents`, `memories`, `plans`, `entities`,
`tasks`, `decisions`, `graph_edges`, and `user_preferences` all at once
touches every existing row in every one of those tables simultaneously,
and the roadmap's own first acceptance criterion requires proving
isolation across all of them adversarially. That is not a "smallest
safe slice" -- it is the single riskiest change this project could make
in one PR.

## Decision

**This phase delivers the foundation only: `Organization` exists, every
user belongs to one, and at least one policy is configurable per
organization -- the roadmap's second acceptance criterion, achieved
honestly. The first acceptance criterion (adversarial tenant isolation
across every table) is explicitly NOT delivered here** and is named as
its own follow-up phase in Consequences, exactly matching what the
roadmap's own design questions already anticipated needing.

**A new `Organization` table** (`id`, `name`, `policies` JSONB,
`created_at`) and **`User.organization_id`** (FK, `NOT NULL`). No
`Team` table yet -- nothing in this codebase needs a grouping *within*
an organization before organizations themselves exist and are used for
anything; that's real future work once there's a second real
organization to group members within.

**Migration approach for `User.organization_id`**: add the column
nullable, backfill every existing user to one auto-created "Default
Organization" row, then alter the column to `NOT NULL` -- the standard
safe pattern for adding a required column to a live table with existing
rows, not adding `NOT NULL` in one step (which would require a
column-wide default with no per-row meaning here). This directly
answers the roadmap's "does the current deployment become one
organization transparently" question: yes, exactly once, in this
migration, non-destructively -- no existing user is disrupted or needs
to re-register.

**One real policy: `approval_required_goals`, overriding Planning
Engine's hardcoded `APPROVAL_REQUIRED_GOALS`** (ADR 0019). An
organization's `policies` JSONB can set
`{"approval_required_goals": [...]}`; `create_plan()` checks the
calling user's organization for an override before falling back to the
module-level default. This is chosen over a synthetic policy invented
just to prove the mechanism -- it's a real, already-existing hardcoded
decision (which goals require human approval before running) that
gains real per-organization configurability, satisfying the roadmap's
second acceptance criterion concretely and testably.

**`GET`/`PUT /organizations/me/policies`, admin-role-only.** Regular
members can't change their organization's approval requirements;
reusing `User.role == "admin"` (ADR 0001) rather than inventing an
org-specific role field, since nothing yet distinguishes "admin of this
org" from "admin" platform-wide -- that distinction is part of the RBAC
2.0 work this phase explicitly does not build.

## Consequences

- **Explicitly deferred, not solved**: `organization_id` on `documents`,
  `memories`, `plans`, `entities`, `tasks`, `decisions`, `graph_edges`,
  `user_preferences`; the adversarial cross-org isolation test the
  roadmap's own first acceptance criterion demands; `Team`s; shared
  memory across a team; AI governance/audit views over
  `ai_call_log`/`reflection_log` by organization; RBAC 2.0 (real
  per-role permission sets replacing the flat `member`/`admin`/`service`
  triad). All are real, named future work -- this phase deliberately
  does not claim to have solved data isolation while only having built
  organizational membership.
- Until that follow-up phase lands, **there is no actual data isolation
  between organizations** -- every document/memory/plan/etc. query in
  this codebase is unchanged and still only scoped by `user_id`, not
  `organization_id`. Two users in different organizations today have
  exactly the same (lack of) cross-user data exposure as before this
  PR; this phase does not weaken anything, it just doesn't yet
  strengthen the multi-tenant case the roadmap ultimately wants.
- The one real policy (`approval_required_goals`) proves the mechanism
  end to end: an organization's admin can make their own org stricter
  (or, in principle, more permissive) than the platform default,
  without touching code.
