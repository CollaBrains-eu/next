# ADR 0028: Phase 13 — Personal AI

## Status
Accepted

## Context

`docs/roadmap/phase-13.md` frames this phase as durable knowledge
*about the user themselves* (preferred language, writing style,
favorite channel, active cases, work patterns, expertise) -- distinct
from Phase 8b's memory, which stores facts extracted *from
conversations*. It proposes three new services
(`services/profile`, `services/preferences`, `services/context`) and
flags three open questions: overlap with Phase 8b memory, explicit vs.
inferred precedence, and privacy/retention.

Its acceptance criteria: one preference set once demonstrably changes
AI behavior across multiple, otherwise-unrelated future conversations
without being re-stated; a user can view and delete their own
preference data.

## Decision

**One preference, one table, no new services.** `preferred_language`
is the roadmap's own example and the smallest concrete thing that can
"demonstrably change AI behavior" in a testable way. No
`services/profile`/`services/context` yet -- those cover active
cases/work patterns/expertise, which don't have a concrete first
consumer today (no code anywhere in this repo currently varies
behavior based on "what case is the user working on"). Building storage
for data nothing reads yet would be exactly the kind of speculative
structure this project has consistently declined (9a's calendar/mail
tools, 9c's unused cost/priority fields, 11's Agent descriptor).

**A new `UserPreference` table, not a fourth `Memory.memory_type`.**
This resolves the roadmap doc's own leaning: preference data is
explicitly set (not extracted by an LLM judging a conversation),
doesn't expire, and has a different write pattern (upsert-by-user, not
append-only). Reusing `Memory`'s `embedding`/`expires_at`/`importance`
columns for data that's meant to be permanent and explicitly authored
would blur two different contracts, the same reasoning the roadmap doc
itself already worked through.

**Explicit only -- no inference in this slice.** The roadmap's second
open question (explicit vs. inferred, and which wins) doesn't need
resolving yet: there's no inference mechanism in this codebase that
could set a preference from observed behavior. Only
`PUT /preferences/me` (the user stating it themselves) exists. Inferring
a language preference from message history is real future work, not
solved speculatively here.

**Privacy is resolved the same way ADR 0025 resolved it for
`Decision`s**: the user who owns the data can view (`GET /preferences/me`)
and delete (`DELETE /preferences/me`) it, and nobody else's role
(including `admin`) can read or write another user's preferences
through these endpoints -- there is no operational need for an admin
override here, unlike `Decision`/`Plan`, so none was added.

**Wired into `/chat` only, as one line in the system prompt.** If
`preferred_language` is set, `chat.py` appends "Respond in
{language}." to the system prompt built for that request. This is the
smallest possible integration that satisfies "changes AI behavior
across multiple, otherwise-unrelated future conversations without
being re-stated" -- no new prompt-construction abstraction, just one
conditional line in the same `_build_messages()` chat.py already has.

## Consequences

- `services/preferences`/`services/context`/`services/profile` as
  separate deployable services (the roadmap's literal proposal) are not
  built -- `api/preferences.py` inside the existing monolith, matching
  every other phase's package-per-concept convention, is the smallest
  safe slice.
- Only `/chat` reads the preference today. `/legal/draft`, the
  Planning Engine, and the Manager Agent (Phase 11) don't consult it --
  extending "respond in the user's preferred language" to those is
  real, deferred future work, not done speculatively for endpoints that
  don't obviously need it yet (a legal draft's language is presumably
  dictated by the matter, not the user's chat preference).
- Work patterns, expertise, and active-case tracking (the roadmap's
  other named preference types) are entirely deferred -- this phase
  proves the mechanism (a durable, explicit, per-user setting that
  measurably changes behavior) with the one example the roadmap itself
  offered, not all of them at once.
