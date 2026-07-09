# ADR 0043: Phase 26 — User Facts (Temporal Memory)

## Status

Accepted

## Context

`docs/superpowers/plans/2026-07-09-fase1-admin-dashboard.md` §3.6
identified temporal fact memory as a gap in both CollaBrains v2 (a flat
key-value `UserKnowledge` table, no validity periods at all) and Next's
own `memories` table (episodic conversation facts, not "what is true
right now" semantics). Neither has anything resembling "address X valid
from date A to date B". The closest reference is v3's unbuilt
`v3/backend/app/models/fact.py` sketch.

## Decision

**Built against Next's own conventions, not v3's unbuilt sketch.**
`user_facts.py::extract_facts_from_document` follows the exact
`entity_agent.py` shape (single `json_mode=True` extraction call,
graceful degradation to `[]` on unparseable output), and `UserFact.status`
reuses Entity's `pending_review`/`confirmed`/`rejected` convention
(ADR 0008, Phase 21's review queue) instead of building a second,
parallel review-queue system the way v3's sketch implied.

**`detect_conflicts` does interval-overlap, not equality, matching.**
Two facts of the same `(user_id, fact_type)` conflict if their
`[valid_from, valid_to)` periods overlap, where an absent `valid_to`
means "still valid" (open-ended). Implemented as a SQLAlchemy `and_(*conditions)`
list built conditionally, not a Python ternary passed as a where-clause
arg -- caught in review before it ever ran, since `.where(x if cond else True)`
only works by accident of SQLAlchemy's boolean coercion and reads as a
plain Python conditional to anyone skimming it.

**`GET /facts` is scoped to the calling user only** (no `user_id` query
param) -- this is personal data; an arbitrary `user_id` filter the way
the original plan sketch described would have been a real authorization
hole (any authenticated user reading anyone else's facts).

**Wired into the event chain like document classification (Phase 23)**,
not a separate trigger: `_handle_extract_facts` subscribes to
`EmbeddingsCreated`, gated by a new `auto_extract_facts_on_ready` setting.

## Consequences

- One new table (`user_facts`), one new router (`facts_router.py`).
- **Real bug caught by the test suite itself, not by inspection**: the
  first version of `test_user_facts.py` passed a bare `uuid4()` as
  `document_id` to `extract_facts_from_document`, which correctly failed
  with a foreign-key violation against the real `documents` table --
  `source_document_id` is a genuine FK, exactly as intended. Fixed by
  creating a real `Document` row in the test fixtures, not by loosening
  the constraint.
- **Same Caddy routing gap hit in Phase 22 (ADR 0039), hit again here**:
  `/facts` had to be added to the Caddyfile's `@api` path matcher.
  Applying the lesson documented there directly this time -- restarted
  the Caddy container rather than relying on `caddy reload`, since the
  Caddyfile is a single-file Docker bind mount that a rsync-based sync
  breaks (temp-file-and-rename changes the inode).
- Full test suite re-run after this change showed the identical 14
  pre-existing failures as every prior phase in this rollout.
