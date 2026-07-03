# Phase 13 — Personal AI

> **Status: done.** Built as one preference, `preferred_language`, in a
> new `UserPreference` table, wired into `/chat`'s system prompt (ADR
> 0028) -- not the three proposed services (profile/preferences/context),
> since the other data (work patterns, expertise, active cases) has no
> concrete first consumer in this codebase yet. See `README.md` for the
> summary. Kept here as historical context for how the open design
> questions got resolved.

## Goal

Give the AI durable knowledge *about a specific user* — preferred
language, writing style, favorite communication channel, active cases,
work patterns, expertise — so it doesn't start every conversation from
zero. This is distinct from Phase 8b's long-term memory, which stores
facts extracted *from conversations* (episodic/semantic/procedural);
Phase 13 stores facts *about the user themselves*, set more deliberately
and changing more slowly.

## Why now

Phase 8b already proved the retrieval-and-inject pattern (embed,
similarity search, inject into the prompt) for conversation-derived
memory. Personal AI reuses that proven mechanism for a different, more
stable category of data — this is an extension of an established
pattern, not a new one.

## New services

```
services/profile
services/preferences
services/context
```

- **profile** — who the user is: role, expertise, active
  cases/clients they're working (likely referencing Phase 10's `Case`
  nodes once that exists).
- **preferences** — how the user wants the AI to behave: preferred
  language, writing style/tone, preferred notification channel (Signal
  vs. email vs. in-app — ties into Phase 9's tool registry once mail
  exists as a tool).
- **context** — working state: what the user is currently focused on,
  recent activity patterns, so a session can resume where the last one
  left off.

## Design questions to resolve before implementation

- **Overlap with Phase 8b memory**: does `Memory.memory_type` grow a
  fourth type (e.g. `profile`), or are these genuinely separate tables?
  Leaning separate — profile/preference data has different lifecycle
  rules (explicitly set or slowly inferred, rarely expires) than
  episodic memory (extracted per-exchange, can expire). Reusing
  `Memory`'s `expires_at`/`importance` machinery for data that's meant
  to be permanent and authoritative would blur two different contracts.
- **Explicit vs. inferred**: preferences most likely need both an
  explicit settings UI (user says "I prefer German") and inference from
  behavior (the AI notices the user always writes back in German) —
  which takes precedence when they conflict?
- **Privacy**: this is inherently more sensitive than episodic memory
  (it's a standing profile of the user, not a transient conversation
  fact) — worth an explicit ADR decision on retention/deletion (a user
  deleting their profile vs. deleting one memory) before storing
  anything here in earnest.

## Acceptance criteria

- At least one preference (e.g. preferred language) is set once and
  demonstrably changes AI behavior across multiple, otherwise-unrelated
  future conversations without being re-stated.
- A user can view and delete their own profile/preference data — this
  should not ship without that, given the privacy sensitivity noted
  above.
